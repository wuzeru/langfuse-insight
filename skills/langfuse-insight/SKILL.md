---
name: langfuse-insight
description: Daily LLM-powered analysis of Langfuse traces to detect user pain points and friction patterns. Use when running daily trace analysis, checking user behavior, finding pain points, identifying iteration explosions, or generating Langfuse insight reports.
---

# langfuse-insight

每天自动分析 Langfuse 追踪数据，发现用户卡点和改进方向。

## 什么时候用

- 定时任务：每天早晨跑一次
- 手动触发：`/langfuse-insight now` 或 `分析昨天的 langfuse 数据`
- 指定日期：`分析 2026-05-06 的 langfuse 数据`

## 工作流

每次分析先创建报告目录，并把本次所有产物放在同一个目录：

```bash
REPORT_DIR=workspace/2026-05-06
mkdir -p "$REPORT_DIR"
```

### 1. 连接数据源

根据配置选择数据源：

**ClickHouse 直连**（自托管 Langfuse v3）：
```bash
python3 skills/langfuse-insight/scripts/query.py --source clickhouse \
  --host macmini-server.local --port 8123 \
  --user clickhouse --password $CK_PASSWORD \
  --project cmnn5pvv40006pk07wbaeoiiu \
  --date 2026-05-06 \
  -o "$REPORT_DIR/raw_data.json"
```

**Langfuse Cloud API**：
```bash
python3 skills/langfuse-insight/scripts/query.py --source langfuse \
  --public-key $LF_PUBLIC_KEY --secret-key $LF_SECRET_KEY \
  --host https://cloud.langfuse.com \
  --project cmnn5pvv40006pk07wbaeoiiu \
  --date 2026-05-06 \
  -o "$REPORT_DIR/raw_data.json"
```

**LiteLLM Proxy**：
```bash
python3 skills/langfuse-insight/scripts/query.py --source litellm \
  --host http://macmini-server.local:4000 \
  --api-key $LITELLM_API_KEY \
  --project litellm \
  --date 2026-05-06 \
  -o "$REPORT_DIR/raw_data.json"
```

输出 `$REPORT_DIR/raw_data.json`：
```json
{
  "date": "2026-05-06",
  "project": "cmnn5pvv40006pk07wbaeoiiu",
  "traces": [...],
  "observations": [...]
}
```

### 2. 统计分析

```bash
python3 skills/langfuse-insight/scripts/analyze.py \
  "$REPORT_DIR/raw_data.json" \
  -o "$REPORT_DIR/analysis.json"
```

`analysis.json` 包含以下维度（纯 Python 计算，不消耗 LLM token）：

| 指标 | 计算方式 |
|------|---------|
| `trace_count` | traces 总数 |
| `user_count` | 去重 user_id |
| `correction_rate` | 用户消息匹配 "不对\|不是\|重新\|少了\|多了\|错了\|改" 的 trace 占比 |
| `explosion_traces` | observation 数 > 15 的 trace 列表 |
| `avg_llm_calls` | 平均每个 trace 的 LLM 调用次数 |
| `model_distribution` | 各模型调用次数 |
| `error_traces` | 含 ERROR level observation 的 trace |
| `session_groups` | 按 session_id 分组的 trace 序列 |

### 3. LLM 解读（强烈推荐）

把统计摘要 + 抽样的关键 trace 发给 LLM，让它解读卡点和建议：

```
你是一个 Langfuse 追踪分析专家。分析以下数据，找出用户的卡点：

## 基础统计
- 日期：2026-05-06
- 项目：h-agent
- traces：32，用户数：0（未配置 user_id）
- 纠正率：34%（11/32 traces 含纠正关键词）
- 迭代爆炸：2 traces 的 LLM 调用 > 15 次

## 纠正 trace 抽样
[列出纠正关键词匹配的 trace 的 input/output 摘要]

## 迭代爆炸 trace 详情
[列出 observation 数 > 15 的 trace 结构]

请输出：
1. Top 3 卡点（每个一句话描述 + 涉及的 trace 数/占比）
2. 每个卡点的根因推测
3. 修复建议（具体、可执行）
4. 和昨天的对比趋势（如果提供了昨天的数据）
```

LLM 解读的结果写入 `$REPORT_DIR/insight.md`。

### 4. 推送报告

```bash
python3 skills/langfuse-insight/scripts/report.py \
  "$REPORT_DIR/insight.md" \
  --feishu $FEISHU_WEBHOOK \
  --save-to "$REPORT_DIR"
```

支持的推送渠道：
- 飞书卡片消息（`--feishu`）
- Slack（`--slack`）
- 存本地文件（`--save-to`，默认建议本次报告目录 `$REPORT_DIR`）
- stdout（不加任何 flag）

## 目录结构

```
langfuse-insight-agent/
├── CLAUDE.md
├── skills/
│   └── langfuse-insight/
│       ├── SKILL.md
│       ├── scripts/
│       │   ├── query.py
│       │   ├── analyze.py
│       │   └── report.py
│       ├── reference/
│       │   ├── correction_patterns.md
│       │   ├── clickhouse_schema.md
│       │   └── feishu_card_spec.md
│       └── config.example.yml
└── workspace/
    └── YYYY-MM-DD/     ← 单次报告的原始数据、分析结果和报告
```

## 怎么用

### 作为 Agent Skill

把整个目录作为 agent 工作区，配置好环境变量：

```bash
export CK_PASSWORD=xxx
export LANGFUSE_PUBLIC_KEY=pk-xxx
export LANGFUSE_SECRET_KEY=sk-xxx
export LITELLM_API_KEY=xxx
export FEISHU_WEBHOOK=https://open.feishu.cn/xxx
```

Agent 会自动在以下情况触发：
- 定时任务触发（例如 h-agent 的 cron）
- 用户说"分析一下昨天的 langfuse 数据"
- 用户说 `/langfuse-insight 2026-05-06`

### 独立使用

```bash
pip install httpx clickhouse-connect

REPORT_DIR=workspace/2026-05-06
mkdir -p "$REPORT_DIR"

python3 skills/langfuse-insight/scripts/query.py --source clickhouse ... \
  -o "$REPORT_DIR/raw_data.json"
python3 skills/langfuse-insight/scripts/analyze.py \
  "$REPORT_DIR/raw_data.json" \
  -o "$REPORT_DIR/analysis.json"
# 把 analysis JSON 的摘要发给你的 LLM 解读，保存为 $REPORT_DIR/insight.md
python3 skills/langfuse-insight/scripts/report.py \
  "$REPORT_DIR/insight.md" \
  --save-to "$REPORT_DIR"
```

## 纠正确认模式

`scripts/analyze.py` 使用的正则：

```
不对|不是|重新|少了|多了|错了|改一下|改改|有问题|不对的|不要|取消|删除|去掉|不是这样的|不对不对|再改|再试试
```

匹配范围：trace 的 `input` 字段（即用户消息）。只匹配中文，避免误判英文 technical content。

如果要增加新模式，编辑 `skills/langfuse-insight/reference/correction_patterns.md`。

## 方法论

这个 skill 的核心假设：

1. **纠正 = 卡点**：用户说"不对"意味着 agent 上次输出有问题
2. **迭代爆炸 = 效率低**：一个 trace 调用 > 15 次 LLM 说明 agent 在徒劳地自我修正
3. **模式比单个 trace 重要**：单个错误可能是偶发，同一模式在多个 trace 中出现才是系统性问题

## 限制

- 只分析文本内容，不分析图片/音频
- LiteLLM 数据源默认只提供请求日志，不包含原始用户输入，因此纠正关键词分析可能为空
- 不支持实时分析（每天跑一次）
- LLM 解读的质量取决于 LLM 本身的理解能力
- 需要 Langfuse 正确配置了 `user_id` 才能区分用户
