# langfuse-insight-agent

Agent workspace for daily LLM-powered analysis of Langfuse traces. Detects user pain points and friction patterns automatically.

## What it does

Every morning, it:
1. Pulls yesterday's traces from Langfuse (API or ClickHouse) or request logs from LiteLLM
2. Analyzes patterns — correction loops, iteration explosions, error clusters
3. Uses an LLM to interpret findings and suggest fixes
4. Pushes a structured report to your chat (飞书 / Slack / stdout)

## Why

LLM tracing tools (Langfuse, LangSmith, etc.) are great at collecting data — but nobody has time to manually read through traces every day. Pain points go unnoticed for weeks.

`langfuse-insight-agent` fills this gap with a project-local agent skill, simple Python scripts, and a dedicated `workspace/` for deliverables.

## Quick start

```bash
cd langfuse-insight-agent
pip install httpx clickhouse-connect
cp skills/langfuse-insight/config.example.yml workspace/config.yml
# edit config.yml with your Langfuse + webhook credentials
REPORT_DIR=workspace/2026-05-06
mkdir -p "$REPORT_DIR"
python3 skills/langfuse-insight/scripts/query.py --source clickhouse ... \
  -o "$REPORT_DIR/raw_data.json"
python3 skills/langfuse-insight/scripts/analyze.py \
  "$REPORT_DIR/raw_data.json" \
  -o "$REPORT_DIR/analysis.json"
```

## Supported data sources

| Source | Setup | Best for |
|--------|-------|----------|
| **Langfuse Cloud API** | `public_key` + `secret_key` | Langfuse Cloud users |
| **ClickHouse direct** | host + credentials | Self-hosted Langfuse (v3+) |
| **LiteLLM proxy** | `api_key` + proxy host | Gateway-level model usage, errors, spend, and latency |

## Supported reporters

| Reporter | Config |
|----------|--------|
| 飞书 (Feishu) | `feishu_webhook` |
| Slack | `slack_webhook` |
| Markdown file | `output_dir` |
| stdout | default |

## Agent layout

```text
langfuse-insight-agent/
├── CLAUDE.md
├── skills/
│   ├── langfuse-insight/
│       ├── SKILL.md
│       ├── scripts/
│       ├── reference/
│       └── config.example.yml
│   └── litellm-insight/
│       └── SKILL.md
└── workspace/
    └── YYYY-MM-DD/
```

All generated deliverables should stay under a per-report directory like `workspace/YYYY-MM-DD/`.

## How analysis works

### Phase 1: Statistical (0 LLM cost)
- Trace count, observation distribution, model usage
- **Correction rate**: traces where user said "不对"/"重新"/"少了"/"错了"
- **Iteration explosion**: traces with >15 LLM calls
- **Error rate**: traces with error-level observations

### Phase 2: LLM interpretation (optional, ~few cents/day)
- Top 3 pain points with root cause hypotheses
- Actionable fix suggestions
- Trend comparison vs previous day

## Config example

```yaml
source:
  type: clickhouse
  clickhouse:
    host: macmini-server.local
    port: 8123
    user: clickhouse
    password: ${CK_PASSWORD}
  litellm:
    host: http://macmini-server.local:4000
    api_key: ${LITELLM_API_KEY}

projects:
  - id: cmnn5pvv40006pk07wbaeoiiu
    name: h-agent

llm:
  enabled: true
  provider: minimax
  api_key: ${MINIMAX_API_KEY}
  model: minimax-m2.7
  base_url: https://api.minimax.chat/v1

report:
  type: feishu
  feishu_webhook: ${FEISHU_WEBHOOK}
  save_dir: ./workspace/
```

## Status

Early stage. See [DESIGN.md](DESIGN.md) for architecture details.

## LiteLLM Source

```bash
python3 skills/langfuse-insight/scripts/query.py --source litellm \
  --host http://macmini-server.local:4000 \
  --api-key "$LITELLM_API_KEY" \
  --project litellm \
  --date 2026-05-07 \
  -o workspace/2026-05-07/litellm_raw_data.json
```

LiteLLM spend logs do not include raw prompts by default, so correction-keyword analysis is limited. The source is useful for model distribution, error rate, latency, token usage, spend, and session grouping.

## License

MIT
