#!/usr/bin/env python3
"""Statistical analysis of Langfuse raw trace data.

Pure Python computation - zero LLM cost.
Takes raw_data.json from query.py, outputs analysis.json.

Usage:
  python3 analyze.py raw_data.json -o analysis.json
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime


# ---------------------------------------------------------------------------
# Correction pattern matching
# ---------------------------------------------------------------------------

# Chinese correction keywords - users expressing disagreement or asking for revision
CORRECTION_PATTERN = re.compile(
    r"不对|不是|重新|少了|多了|错了|改一下|改改|有问题|不对的"
    r"|不要|取消|删除|去掉|不是这样的|不对不对|再改|再试试"
)


def _trace_inputs(trace: dict) -> list[str]:
    """Collect all text inputs from a trace (user messages)."""
    inputs = []
    inp = trace.get("input")
    if isinstance(inp, str):
        inputs.append(inp)
    elif isinstance(inp, list):
        # Langfuse structured input: [{"role": "user", "content": "..."}]
        for msg in inp:
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str):
                    inputs.append(content)
    return inputs


def _trace_outputs(trace: dict) -> list[str]:
    """Collect all text outputs from a trace."""
    outputs = []
    out = trace.get("output")
    if isinstance(out, str):
        outputs.append(out)
    elif isinstance(out, dict):
        outputs.append(out.get("content", str(out)))
    return outputs


def detect_correction(trace: dict) -> bool:
    """Check if any user message in this trace contains correction keywords."""
    for text in _trace_inputs(trace):
        if CORRECTION_PATTERN.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def analyze(raw: dict) -> dict:
    traces = raw.get("traces", [])
    observations = raw.get("observations", [])

    obs_by_trace: dict[str, list[dict]] = {}
    for obs in observations:
        tid = obs.get("trace_id")
        if tid:
            obs_by_trace.setdefault(tid, []).append(obs)

    trace_count = len(traces)
    user_ids = {t.get("user_id") for t in traces if t.get("user_id")}
    user_count = len(user_ids)

    correction_traces = [t for t in traces if detect_correction(t)]
    correction_rate = round(len(correction_traces) / trace_count, 3) if trace_count else 0

    correction_samples = []
    for t in correction_traces[:5]:
        correction_samples.append({
            "trace_id": t.get("id"),
            "name": t.get("name"),
            "session_id": t.get("session_id"),
            "inputs": _trace_inputs(t)[:3],
        })

    explosion_traces = []
    for t in traces:
        tid = t.get("id")
        obs_count = len(obs_by_trace.get(tid, []))
        if obs_count > 15:
            explosion_traces.append({
                "trace_id": tid,
                "name": t.get("name"),
                "user_id": t.get("user_id"),
                "observation_count": obs_count,
            })

    total_llm_calls = sum(
        1 for o in observations if str(o.get("type", "")).lower() == "generation"
    )
    avg_llm_calls = round(total_llm_calls / trace_count, 1) if trace_count else 0

    model_counter: Counter = Counter()
    for o in observations:
        model = o.get("model")
        if model:
            model_counter[model] += 1
    model_distribution = dict(model_counter.most_common())

    error_obs = [o for o in observations if o.get("level") == "ERROR"]
    error_trace_ids = {o.get("trace_id") for o in error_obs if o.get("trace_id")}
    error_traces = [
        {
            "trace_id": tid,
            "error_count": sum(1 for o in error_obs if o.get("trace_id") == tid),
        }
        for tid in error_trace_ids
    ]

    session_map: dict[str, list[dict]] = {}
    for t in traces:
        sid = t.get("session_id")
        if sid:
            session_map.setdefault(sid, []).append(t)
    session_groups = {
        sid: [t.get("id") for t in tlist]
        for sid, tlist in session_map.items()
    }

    durations = []
    for t in traces:
        ts = t.get("timestamp")
        if ts:
            try:
                start = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                continue
            tid = t.get("id")
            trace_obs = obs_by_trace.get(tid, [])
            latest = start
            for o in trace_obs:
                for key in ("end_time", "start_time"):
                    ot = o.get(key)
                    if ot:
                        try:
                            ot_dt = datetime.fromisoformat(ot)
                            if ot_dt > latest:
                                latest = ot_dt
                        except (ValueError, TypeError):
                            pass
            durations.append((latest - start).total_seconds())

    avg_duration_s = round(sum(durations) / len(durations), 1) if durations else 0
    p95_duration_s = (
        round(sorted(durations)[int(len(durations) * 0.95)], 1) if durations else 0
    )

    abandoned = []
    for sid, tlist in session_map.items():
        if len(tlist) <= 2:
            has_output = any(t.get("output") for t in tlist)
            if not has_output:
                abandoned.append(sid)

    return {
        "date": raw.get("date"),
        "project": raw.get("project"),
        "summary": {
            "trace_count": trace_count,
            "user_count": user_count,
            "correction_rate": correction_rate,
            "correction_count": len(correction_traces),
            "explosion_count": len(explosion_traces),
            "avg_llm_calls": avg_llm_calls,
            "error_count": len(error_traces),
            "error_rate": round(len(error_traces) / trace_count, 3) if trace_count else 0,
            "avg_duration_s": avg_duration_s,
            "p95_duration_s": p95_duration_s,
            "session_count": len(session_groups),
            "abandoned_sessions": len(abandoned),
        },
        "correction": {
            "rate": correction_rate,
            "count": len(correction_traces),
            "samples": correction_samples,
        },
        "explosions": explosion_traces,
        "errors": error_traces,
        "model_distribution": model_distribution,
        "session_groups": session_groups,
        "abandoned_sessions": abandoned,
        "trace_ids": [t.get("id") for t in traces],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Langfuse raw trace data"
    )
    parser.add_argument("input", help="raw_data.json from query.py")
    parser.add_argument("-o", "--output", default="analysis.json", help="Output file")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        raw = json.load(f)

    result = analyze(raw)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    summary = result["summary"]
    print(
        f"[done] {summary['trace_count']} traces | "
        f"{summary['user_count']} users | "
        f"correction: {summary['correction_rate']:.1%} "
        f"({summary['correction_count']}) | "
        f"explosion: {summary['explosion_count']} | "
        f"errors: {summary['error_count']} | "
        f"avg LLM calls: {summary['avg_llm_calls']}"
    )
    print(f"  -> {args.output}")


if __name__ == "__main__":
    main()
