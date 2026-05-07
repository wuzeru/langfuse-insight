#!/usr/bin/env python3
"""Pull Langfuse trace data from ClickHouse or Langfuse Cloud API.

Usage:
  python3 query.py --source clickhouse \
    --host localhost --port 8123 \
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
        obs_rows = client.query(
            """
            SELECT
                id, trace_id, name, type, level,
                start_time, end_time, parent_observation_id, metadata, model, input, output
            FROM observations
            WHERE trace_id IN {trace_ids:Array(String)}
              AND start_time >= {start:DateTime64(3)}
              AND start_time <  {end:DateTime64(3)}
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
        "--source", choices=["clickhouse", "langfuse"], required=True,
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
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--user", default="clickhouse")
    parser.add_argument("--password", default=None)

    # Langfuse API flags
    parser.add_argument("--public-key", default=None)
    parser.add_argument("--secret-key", default=None)

    parser.add_argument(
        "-o", "--output", default=None,
        help="Output file path (default: raw_data.json)"
    )

    args = parser.parse_args()

    # Load secrets from env as fallback
    password = args.password or os.environ.get("CK_PASSWORD")
    public_key = args.public_key or os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = args.secret_key or os.environ.get("LANGFUSE_SECRET_KEY")

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
    else:
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

    output_path = args.output or "raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[done] {len(result['traces'])} traces, "
          f"{len(result['observations'])} observations -> {output_path}")


if __name__ == "__main__":
    main()
