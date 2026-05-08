---
name: litellm-insight
description: Use when analyzing LiteLLM proxy spend logs, model usage, gateway errors, latency, token usage, cost, user activity, or generating LiteLLM insight reports.
---

# litellm-insight

分析 LiteLLM Proxy 的请求日志，识别模型使用、网关错误、token/费用、延迟和用户活动趋势。

## 什么时候用

- 手动触发：`分析昨天的 litellm 数据`、`看一下 LiteLLM 使用情况`
- 指定日期：`分析 2026-05-07 的 litellm`
- 关注网关层指标：模型分布、错误率、token/费用、延迟、用户或 session 活动

## 工作流

每次分析先创建报告目录，并把本次所有产物放在同一个目录：

```bash
REPORT_DIR=workspace/2026-05-07/litellm
mkdir -p "$REPORT_DIR"
```

### 1. 拉取 LiteLLM 日志

优先从环境变量读取 key，不要把 key 写入仓库：

```bash
export LITELLM_API_KEY=xxx
```

从 LiteLLM Proxy 拉取 spend logs，并转换成通用 `raw_data.json`：

```bash
python3 skills/langfuse-insight/scripts/query.py --source litellm \
  --host http://macmini-server.local:4000 \
  --api-key "$LITELLM_API_KEY" \
  --project litellm \
  --date 2026-05-07 \
  -o "$REPORT_DIR/raw_data.json"
```

输出结构与 Langfuse source 一致：

```json
{
  "date": "2026-05-07",
  "project": "litellm",
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

重点查看：

| 指标 | 含义 |
|------|------|
| `trace_count` | LiteLLM 请求数 |
| `user_count` | 去重用户数 |
| `model_distribution` | 模型调用分布 |
| `error_count` / `error_rate` | 网关或模型调用失败情况 |
| `avg_duration_s` / `p95_duration_s` | 请求耗时 |
| `avg_llm_calls` | 每个请求映射为一次 generation，通常接近 1 |

### 3. LLM 解读

把 `analysis.json` 和必要的 `raw_data.json` 抽样交给 LLM 解读，重点关注：

1. Top 模型和高成本模型
2. 错误率异常的模型、用户或时间段
3. 高延迟请求和 P95 变化
4. token/费用异常增长
5. 可执行的治理建议（限流、路由、缓存、模型替换、key 管理）

LLM 解读结果写入：

```bash
$REPORT_DIR/insight.md
```

### 4. 推送报告

```bash
python3 skills/langfuse-insight/scripts/report.py \
  "$REPORT_DIR/insight.md" \
  --feishu "$FEISHU_WEBHOOK" \
  --save-to "$REPORT_DIR"
```

## 远端默认信息

- 默认 host：`http://macmini-server.local:4000`
- `macmini2` 的 SSH 别名通常是 `zeru.wu.macmini2`
- 管理 key 只通过 `LITELLM_API_KEY` 或 `--api-key` 传入，不写入文档、配置或提交

## 限制

- LiteLLM spend logs 默认不包含原始用户输入，因此纠正关键词分析通常为空。
- 这不是 Langfuse trace 分析；它更适合看网关层的使用量、成本、错误和延迟。
- 如果需要用户卡点、对话内容和多轮纠正，请使用 `langfuse-insight`。
