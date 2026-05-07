# langfuse-insight-agent

这个目录是一个面向 Langfuse 追踪分析的 agent 工作区。

## Agent 使用规则

- 优先使用项目内 `skills/` 下的能力完成任务。
- 当前可用 skill：`skills/langfuse-insight/`，用于分析 Langfuse traces、识别用户卡点、生成日报并推送报告。
- 如需临时产出原始数据、分析结果、报告草稿、调试日志或导出文件，统一放到当前目录的 `workspace/` 中。
- 不要把密钥、token、webhook URL 或生产数据提交到仓库；敏感配置通过环境变量提供。

## 交付物目录

所有交付物放在：

```bash
workspace/
```

建议命名：

- `workspace/raw_data_YYYY-MM-DD.json`
- `workspace/analysis_YYYY-MM-DD.json`
- `workspace/insight_YYYY-MM-DD.md`
- `workspace/report_YYYY-MM-DD.md`

## 常用流程

从项目根目录执行：

```bash
python3 skills/langfuse-insight/scripts/query.py --source clickhouse \
  --project cmnn5pvv40006pk07wbaeoiiu \
  --date 2026-05-06 \
  -o workspace/raw_data_2026-05-06.json

python3 skills/langfuse-insight/scripts/analyze.py \
  workspace/raw_data_2026-05-06.json \
  -o workspace/analysis_2026-05-06.json

python3 skills/langfuse-insight/scripts/report.py \
  workspace/insight_2026-05-06.md \
  --save-to workspace/
```
