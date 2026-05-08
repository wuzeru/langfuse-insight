# langfuse-insight-agent

这个目录是一个面向 Langfuse 追踪分析的 agent 工作区。

## Agent 使用规则

- 优先使用项目内 `skills/` 下的能力完成任务。
- 当前可用 skill：
  - `skills/langfuse-insight/`：分析 Langfuse traces、识别用户卡点、生成日报并推送报告。
  - `skills/litellm-insight/`：分析 LiteLLM Proxy 请求日志、模型使用、错误率、延迟和费用。
- 如需临时产出原始数据、分析结果、报告草稿、调试日志或导出文件，统一放到当前目录的 `workspace/` 中，并按单次报告创建子目录。
- 不要把密钥、token、webhook URL 或生产数据提交到仓库；敏感配置通过环境变量提供。

## 交付物目录

所有交付物放在：

```bash
workspace/YYYY-MM-DD/
```

建议命名：

- `workspace/YYYY-MM-DD/raw_data.json`
- `workspace/YYYY-MM-DD/analysis.json`
- `workspace/YYYY-MM-DD/insight.md`
- `workspace/YYYY-MM-DD/report.md`

## 常用流程

从项目根目录执行：

```bash
REPORT_DIR=workspace/2026-05-06
mkdir -p "$REPORT_DIR"

python3 skills/langfuse-insight/scripts/query.py --source clickhouse \
  --host macmini-server.local \
  --project cmnn5pvv40006pk07wbaeoiiu \
  --date 2026-05-06 \
  -o "$REPORT_DIR/raw_data.json"

python3 skills/langfuse-insight/scripts/analyze.py \
  "$REPORT_DIR/raw_data.json" \
  -o "$REPORT_DIR/analysis.json"

python3 skills/langfuse-insight/scripts/report.py \
  "$REPORT_DIR/insight.md" \
  --save-to "$REPORT_DIR"
```

LiteLLM 网关分析使用：

```bash
REPORT_DIR=workspace/2026-05-07/litellm
mkdir -p "$REPORT_DIR"

python3 skills/langfuse-insight/scripts/query.py --source litellm \
  --host http://macmini-server.local:4000 \
  --api-key "$LITELLM_API_KEY" \
  --project litellm \
  --date 2026-05-07 \
  -o "$REPORT_DIR/raw_data.json"
```
