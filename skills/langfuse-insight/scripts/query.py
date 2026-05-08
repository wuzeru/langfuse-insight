#!/usr/bin/env python3
"""Pull trace-like analysis data from Langfuse or LiteLLM.

Usage:
  python3 query.py --source clickhouse \
    --host macmini-server.local --port 8123 \
    --user clickhouse --password xxx \
    --project cmnn5pvv40006pk07wbaeoiiu \
    --date 2026-05-06 \
    --limit 500

  python3 query.py --source langfuse \
    --public-key pk-xxx --secret-key sk-xxx \
    --host https://cloud.langfuse.com \
    --project cmnn5pvv40006pk07wbaeoiiu \
    --date 2026-05-06 \
    --limit 500

  python3 query.py --source litellm \
    --host http://macmini-server.local:4000 \
    --api-key $LITELLM_API_KEY \
    --project litellm \
    --date 2026-05-06 \
    --limit 500

Output: raw_data.json with structure:
{
  "date": "2026-05-06",
  "project": "cmnn5pvv40006pk07wbaeoiiu",
  "traces": [...],
  "observations": [...]
}
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta


# ---------------------------------------------------------------------------
# ClickHouse source
# ---------------------------------------------------------------------------

def query_clickhouse(host: str, port: int, user: str, password: str,
                     project_id: str, target_date: date,
                     limit: int, timeout: int = 60) -> dict:
    """Query traces and observations directly from ClickHouse."""
    try:
        from clickhouse_connect import get_client
    except ImportError:
        sys.exit(
            "clickhouse-connect not installed.\n"
            "  pip install clickhouse-connect"
        )

    client = get_client(
        host=host, port=port,
        username=user, password=password,
        connect_timeout=timeout,
    )

    start_ts = datetime.combine(target_date, datetime.min.time())
    end_ts = start_ts + timedelta(days=1)

    # Fetch traces
    traces = client.query(
        """
        SELECT
            id, name, project_id, user_id, session_id,
            timestamp, metadata, tags, environment, input, output
        FROM traces
        WHERE project_id = {project_id:String}
          AND timestamp >= {start:DateTime64(3)}
          AND timestamp <  {end:DateTime64(3)}
        ORDER BY timestamp ASC
        LIMIT {limit:UInt32}
        """,
        parameters={
            "project_id": project_id,
            "start": start_ts,
            "end": end_ts,
            "limit": limit,
        },
    )

    trace_ids = [row[0] for row in traces.result_rows]
    traces_json = [
        {
            "id": r[0], "name": r[1], "project_id": r[2],
            "user_id": r[3], "session_id": r[4],
            "timestamp": r[5].isoformat() if r[5] else None,
            "metadata": r[6], "tags": r[7],
            "environment": r[8], "input": r[9], "output": r[10],
        }
        for r in traces.result_rows
    ]

    # Fetch observations for these traces
    observations = []
    if trace_ids:
        obs_columns = {
            row[0] for row in client.query("DESCRIBE TABLE observations").result_rows
        }
        if "model" in obs_columns:
            model_expr = "model"
        elif "provided_model_name" in obs_columns:
            model_expr = "provided_model_name"
        elif "internal_model_id" in obs_columns:
            model_expr = "internal_model_id"
        else:
            model_expr = "CAST(NULL, 'Nullable(String)')"

        obs_rows = client.query(
            f"""
            SELECT
                id, trace_id, name, type, level,
                start_time, end_time, parent_observation_id, metadata, {model_expr} AS model, input, output
            FROM observations
            WHERE trace_id IN {{trace_ids:Array(String)}}
              AND start_time >= {{start:DateTime64(3)}}
              AND start_time <  {{end:DateTime64(3)}}
            ORDER BY trace_id, start_time ASC
            """,
            parameters={
                "trace_ids": trace_ids,
                "start": start_ts,
                "end": end_ts,
            },
        )
        observations = [
            {
                "id": r[0], "trace_id": r[1], "name": r[2],
                "type": r[3], "level": r[4],
                "start_time": r[5].isoformat() if r[5] else None,
                "end_time": r[6].isoformat() if r[6] else None,
                "parent_observation_id": r[7], "metadata": r[8],
                "model": r[9], "input": r[10], "output": r[11],
            }
            for r in obs_rows.result_rows
        ]

    return {
        "date": str(target_date),
        "project": project_id,
        "traces": traces_json,
        "observations": observations,
    }


# ---------------------------------------------------------------------------
# LiteLLM proxy source
# ---------------------------------------------------------------------------

def _first_non_empty(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _litellm_error_info(log: dict) -> dict:
    metadata = log.get("metadata") or {}
    error = metadata.get("error_information") or {}
    if isinstance(error, dict):
        return error
    return {"error_message": str(error)} if error else {}


def _litellm_user_id(log: dict):
    metadata = log.get("metadata") or {}
    return _first_non_empty(
        log.get("user"),
        log.get("end_user"),
        metadata.get("user_api_key_user_id"),
        metadata.get("user_api_key_alias"),
    )


def litellm_log_to_trace(log: dict, project_id: str, target_date: date) -> dict:
    """Convert one LiteLLM spend log row into the common trace shape."""
    metadata = log.get("metadata") or {}
    model = _first_non_empty(log.get("model"), log.get("model_group"), "unknown")
    call_type = _first_non_empty(log.get("call_type"), "request")

    return {
        "id": log.get("request_id"),
        "name": f"{call_type}: {model}",
        "project_id": project_id,
        "user_id": _litellm_user_id(log),
        "session_id": log.get("session_id"),
        "timestamp": _first_non_empty(log.get("startTime"), str(target_date)),
        "metadata": {
            "source": "litellm",
            "status": log.get("status"),
            "call_type": log.get("call_type"),
            "model_group": log.get("model_group"),
            "api_key_alias": metadata.get("user_api_key_alias"),
            "team_id": _first_non_empty(log.get("team_id"), metadata.get("user_api_key_team_id")),
            "request_duration_ms": log.get("request_duration_ms"),
            "spend": log.get("spend"),
            "total_tokens": log.get("total_tokens"),
        },
        "tags": log.get("request_tags") or [],
        "environment": None,
        "input": None,
        "output": None,
    }


def litellm_log_to_observation(log: dict) -> dict:
    """Convert one LiteLLM spend log row into a generation observation."""
    error = _litellm_error_info(log)
    status = str(log.get("status") or "").lower()
    level = "ERROR" if status in {"failure", "failed", "error"} or error else "DEFAULT"

    metadata = {
        "source": "litellm",
        "status": log.get("status"),
        "spend": log.get("spend"),
        "total_tokens": log.get("total_tokens"),
        "prompt_tokens": log.get("prompt_tokens"),
        "completion_tokens": log.get("completion_tokens"),
        "request_duration_ms": log.get("request_duration_ms"),
        "cache_hit": log.get("cache_hit"),
    }
    if error:
        metadata["error_code"] = _first_non_empty(error.get("error_code"), error.get("code"))
        metadata["error_message"] = _first_non_empty(
            error.get("error_message"),
            error.get("message"),
            str(error),
        )

    request_id = log.get("request_id")
    return {
        "id": f"{request_id}:generation",
        "trace_id": request_id,
        "name": log.get("call_type") or "generation",
        "type": "generation",
        "level": level,
        "start_time": log.get("startTime"),
        "end_time": log.get("endTime"),
        "parent_observation_id": None,
        "metadata": metadata,
        "model": _first_non_empty(log.get("model"), log.get("model_group")),
        "input": None,
        "output": None,
    }


def _normalize_litellm_host(host: str, port: int) -> str:
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"http://{host}:{port}".rstrip("/")


def query_litellm(api_key: str, host: str, port: int,
                  project_id: str, target_date: date,
                  limit: int, timeout: int = 60) -> dict:
    """Query request spend logs from LiteLLM proxy and normalize them."""
    try:
        import httpx
    except ImportError:
        sys.exit(
            "httpx not installed.\n"
            "  pip install httpx"
        )

    base = _normalize_litellm_host(host, port)
    start_date = str(target_date)
    end_date = str(target_date + timedelta(days=1))
    headers = {"Authorization": f"Bearer {api_key}"}
    logs = []
    page = 1
    page_size = min(100, max(1, limit))

    with httpx.Client(timeout=timeout, headers=headers) as client:
        while len(logs) < limit:
            resp = client.get(
                f"{base}/spend/logs/v2",
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "page": page,
                    "page_size": page_size,
                    "sort_by": "startTime",
                    "sort_order": "asc",
                },
            )
            if resp.status_code != 200:
                print(f"[warn] LiteLLM returned {resp.status_code}: {resp.text[:200]}")
                break

            data = resp.json()
            batch = data.get("data", [])
            if not batch:
                break
            logs.extend(batch)
            if page >= int(data.get("total_pages") or page):
                break
            page += 1

    selected_logs = logs[:limit]
    traces = [
        litellm_log_to_trace(log, project_id=project_id, target_date=target_date)
        for log in selected_logs
        if log.get("request_id")
    ]
    observations = [
        litellm_log_to_observation(log)
        for log in selected_logs
        if log.get("request_id")
    ]

    return {
        "date": str(target_date),
        "project": project_id,
        "traces": traces,
        "observations": observations,
    }


# ---------------------------------------------------------------------------
# Langfuse Cloud API source
# ---------------------------------------------------------------------------

def query_langfuse_api(public_key: str, secret_key: str, host: str,
                       project_id: str, target_date: date,
                       limit: int, timeout: int = 60) -> dict:
    """Query traces via Langfuse Cloud REST API with pagination."""
    try:
        import httpx
    except ImportError:
        sys.exit(
            "httpx not installed.\n"
            "  pip install httpx"
        )

    start_ts = datetime.combine(target_date, datetime.min.time())
    end_ts = start_ts + timedelta(days=1)

    auth = (public_key, secret_key)
    base = host.rstrip("/")
    headers = {"Content-Type": "application/json"}

    all_traces = []
    all_observations = []
    page = 1

    with httpx.Client(auth=auth, timeout=timeout) as client:
        while len(all_traces) < limit:
            resp = client.get(
                f"{base}/api/public/traces",
                params={
                    "project_id": project_id,
                    "fromTimestamp": start_ts.isoformat() + "Z",
                    "toTimestamp": end_ts.isoformat() + "Z",
                    "page": page,
                    "limit": min(100, limit),
                    "orderBy": "timestamp.asc",
                },
                headers=headers,
            )
            if resp.status_code != 200:
                print(f"[warn] API returned {resp.status_code}: {resp.text[:200]}")
                break

            data = resp.json()
            batch = data.get("data", [])
            if not batch:
                break
            all_traces.extend(batch)

            # Fetch observations per trace
            for trace in batch:
                obs_page = 1
                while True:
                    obs_resp = client.get(
                        f"{base}/api/public/observations",
                        params={
                            "traceId": trace["id"],
                            "page": obs_page,
                            "limit": 100,
                        },
                        headers=headers,
                    )
                    if obs_resp.status_code != 200:
                        break
                    obs_data = obs_resp.json()
                    obs_batch = obs_data.get("data", [])
                    if not obs_batch:
                        break
                    all_observations.extend(obs_batch)
                    obs_page += 1

            page += 1

    return {
        "date": str(target_date),
        "project": project_id,
        "traces": all_traces[:limit],
        "observations": all_observations,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date: {s}, expected YYYY-MM-DD"
        ) from exc


def main():
    parser = argparse.ArgumentParser(
        description="Pull Langfuse trace data for a given date"
    )
    parser.add_argument(
        "--source", choices=["clickhouse", "langfuse", "litellm"], required=True,
        help="Data source type"
    )
    parser.add_argument(
        "--date", type=parse_date,
        default=date.today() - timedelta(days=1),
        help="Target date, YYYY-MM-DD (default: yesterday)"
    )
    parser.add_argument(
        "--project", required=True,
        help="Langfuse project ID"
    )
    parser.add_argument(
        "--limit", type=int, default=500,
        help="Max traces to fetch (default: 500)"
    )

    # ClickHouse flags
    parser.add_argument(
        "--host",
        default=os.environ.get("CLICKHOUSE_HOST", "macmini-server.local"),
        help="ClickHouse, Langfuse API, or LiteLLM host",
    )
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--user", default="clickhouse")
    parser.add_argument("--password", default=None)

    # Langfuse API flags
    parser.add_argument("--public-key", default=None)
    parser.add_argument("--secret-key", default=None)
    parser.add_argument("--api-key", default=None, help="LiteLLM proxy API key")

    parser.add_argument(
        "-o", "--output", default=None,
        help="Output file path (default: raw_data.json)"
    )

    args = parser.parse_args()

    # Load secrets from env as fallback
    password = args.password or os.environ.get("CK_PASSWORD")
    public_key = args.public_key or os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = args.secret_key or os.environ.get("LANGFUSE_SECRET_KEY")
    api_key = args.api_key or os.environ.get("LITELLM_API_KEY")

    if args.source == "clickhouse":
        if not password:
            sys.exit("ClickHouse password required: --password or $CK_PASSWORD")
        result = query_clickhouse(
            host=args.host, port=args.port,
            user=args.user, password=password,
            project_id=args.project,
            target_date=args.date,
            limit=args.limit,
        )
    elif args.source == "langfuse":
        if not public_key or not secret_key:
            sys.exit(
                "Langfuse credentials required: "
                "--public-key/--secret-key or $LANGFUSE_PUBLIC_KEY/$LANGFUSE_SECRET_KEY"
            )
        result = query_langfuse_api(
            public_key=public_key, secret_key=secret_key,
            host=args.host,
            project_id=args.project,
            target_date=args.date,
            limit=args.limit,
        )
    else:
        if not api_key:
            sys.exit("LiteLLM API key required: --api-key or $LITELLM_API_KEY")
        litellm_host = args.host
        if litellm_host == "macmini-server.local":
            litellm_host = os.environ.get("LITELLM_HOST", "http://macmini-server.local:4000")
        litellm_port = 4000 if args.port == 8123 else args.port
        result = query_litellm(
            api_key=api_key,
            host=litellm_host,
            port=litellm_port,
            project_id=args.project,
            target_date=args.date,
            limit=args.limit,
        )

    output_path = args.output or "raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[done] {len(result['traces'])} traces, "
          f"{len(result['observations'])} observations -> {output_path}")


if __name__ == "__main__":
    main()
