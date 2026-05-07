# langfuse-insight Design

## Architecture

```
cron (daily 08:00)
    │
    ▼
insight.py  ─────────────────────────────────────────
    │
    ├──[1] source.load(project_id, lookback_days=1)
    │       ├── langfuse_api.py   ← Langfuse Cloud REST API
    │       └── clickhouse.py     ← ClickHouse direct SQL
    │       输出: RawData { traces[], observations[] }
    │
    ├──[2] analyzer.analyze(raw_data)
    │       ├── stats.py          ← 基础统计
    │       ├── correction.py     ← 纠正模式 → correction_rate, top_corrections
    │       └── iteration.py      ← 迭代爆炸 → explosion_traces[]
    │       输出: Analysis { stats, corrections, explosions, ... }
    │
    ├──[3] llm.interpret(analysis)  [optional]
    │       输入: 统计摘要 + 抽样关键 trace
    │       输出: Insight { pain_points[], suggestions[] }
    │
    └──[4] reporter.send(report)
            ├── feishu.py         ← 飞书卡片消息
            ├── slack.py          ← Slack Block Kit
            ├── markdown.py       ← 本地文件
            └── stdout.py         ← 终端打印
```

## Key design decisions

### 1. Analysis is LLM-optional
All core metrics (correction rate, iteration explosion, error count) are computed in pure Python. LLM is only used for the final "interpret and suggest" step, which can be turned off with `llm.enabled: false`.

### 2. Stateless
No database. No long-running process. Each run is a standalone execution:
- Input: yesterday's traces from Langfuse
- Output: one report (webhook + optional local file)
- Comparison data (trends) can optionally read yesterday's `reports/YYYY-MM-DD.json`

### 3. Project-agnostic
The tool knows nothing about the business domain. It detects pain points through **generic behavioral patterns**:
- Correction loops (user disagrees with agent output)
- Excessive iteration (too many LLM calls in one trace)
- Errors/exceptions
- Abandoned sessions

### 4. Plug-in data sources
Each source implements a simple interface:
```python
class Source(Protocol):
    def load(self, project_id: str, date: date) -> RawData: ...
```

Adding a new source (e.g., LangSmith, Phoenix) just means implementing this interface.

## Pain point detection heuristics

| Pattern | Detection method | Severity |
|---------|-----------------|----------|
| Correction loop | User message matches "不对\|不是\|重新\|少了\|多了\|错了\|改一下" | HIGH |
| Iteration explosion | `count(observations) > 15` in single trace | HIGH |
| Early abandonment | Session has only 1-2 traces, no completed output | MEDIUM |
| Repeated same task | Same trace name appears 3+ times in short window | MEDIUM |
| Slow response | `avg(duration) > 30s` for generation observations | LOW |
| Rising errors | Error count today > 2x yesterday | HIGH |

## Report format (飞书)

```
📊 Langfuse 日报 | 2026-05-06

───────────────────────
h-agent
  traces: 32  (+5 vs 昨天)
  纠正率: 34% (11/32 traces 有纠正)
  迭代爆炸: 2 traces (>15次LLM调用)
───────────────────────

🔴 Top 3 卡点

1. 报价单字段填错位置 — 型号列出现人名
   涉及 11/32 traces (34%)
   特征：用户反复说"型号不对""底钉钉不对"
   💡 建议：增强 template_detect 识别中文占位符

2. 格式细节多轮修正 — 空白/居中等
   涉及 7/32 traces (22%)
   特征："表格紧凑""标题居中""空格删除"
   💡 建议：报价模板预设排版规则，减少手动调整

3. 内容遗漏 — 缺少维修描述
   涉及 3/32 traces (9%)
   特征："少了一些内容""前缀没有"
   💡 建议：生成后做字段完整性校验

───────────────────────
📈 趋势：纠正率较昨天上升 12%
```

## Configuration

See `skills/langfuse-insight/config.example.yml` for full configuration reference.

Key config sections:
- `source`: data source (clickhouse / langfuse_api)
- `projects`: list of projects to analyze
- `llm`: LLM provider settings (optional)
- `report`: output reporter + webhook URLs
- `analyze`: analysis thresholds and toggles
