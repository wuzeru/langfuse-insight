# langfuse-insight

Daily LLM-powered analysis of Langfuse traces. Detects user pain points and friction patterns automatically.

## What it does

Every morning, it:
1. Pulls yesterday's traces from Langfuse (API or ClickHouse)
2. Analyzes patterns — correction loops, iteration explosions, error clusters
3. Uses an LLM to interpret findings and suggest fixes
4. Pushes a structured report to your chat (飞书 / Slack / stdout)

## Why

LLM tracing tools (Langfuse, LangSmith, etc.) are great at collecting data — but nobody has time to manually read through traces every day. Pain points go unnoticed for weeks.

`langfuse-insight` fills this gap with **zero additional infrastructure**: one Python script, one cron job, one webhook.

## Quick start

```bash
git clone https://github.com/wuzeru/langfuse-insight.git
cd langfuse-insight
pip install -r requirements.txt
cp config.example.yml config.yml
# edit config.yml with your Langfuse + webhook credentials
python insight.py
```

## Supported data sources

| Source | Setup | Best for |
|--------|-------|----------|
| **Langfuse Cloud API** | `public_key` + `secret_key` | Langfuse Cloud users |
| **ClickHouse direct** | host + credentials | Self-hosted Langfuse (v3+) |

## Supported reporters

| Reporter | Config |
|----------|--------|
| 飞书 (Feishu) | `feishu_webhook` |
| Slack | `slack_webhook` |
| Markdown file | `output_dir` |
| stdout | default |

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
    host: localhost
    port: 8123
    user: clickhouse
    password: ${CK_PASSWORD}

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
  save_dir: ./reports/
```

## Status

Early stage. See [DESIGN.md](DESIGN.md) for architecture details.

## License

MIT
