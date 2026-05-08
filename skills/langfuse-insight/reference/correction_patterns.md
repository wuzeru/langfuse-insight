# Correction Patterns

## Current regex

```
不对|不是|重新|少了|多了|错了|改一下|改改|有问题|不对的|不要|取消|删除|去掉|不是这样的|不对不对|再改|再试试
```

## How to extend

Edit the `CORRECTION_PATTERN` regex in `skills/langfuse-insight/scripts/analyze.py`.

### Pattern categories

| Category | Keywords | Meaning |
|----------|----------|---------|
| 直接否定 | 不对, 不是, 错的 | User outright rejects output |
| 重新请求 | 重新, 再改, 再试试 | User wants a do-over |
| 数量不对 | 少了, 多了 | Missing or extra content |
| 错误指出 | 错了, 有问题 | Something is wrong |
| 微调请求 | 改一下, 改改 | Minor revision needed |
| 删除请求 | 不要, 取消, 删除, 去掉 | Remove something |

### Adding new patterns

1. Add to the regex alternation group (pipe-separated)
2. Update the table above
3. Test with a dry run:

```bash
REPORT_DIR=workspace/2026-05-06
mkdir -p "$REPORT_DIR"

python3 skills/langfuse-insight/scripts/analyze.py \
  "$REPORT_DIR/raw_data.json" \
  -o "$REPORT_DIR/analysis.json"
python3 -c "
import json
d = json.load(open('$REPORT_DIR/analysis.json'))
print(f'Correction rate: {d[\"correction\"][\"rate\"]:.1%}')
for s in d['correction']['samples']:
    for inp in s['inputs']:
        print(f'  [{s[\"trace_id\"][:8]}] {inp[:120]}')
"
```

### Known limits

- Patterns are substring matches, not semantic. "不是" in a non-disagreement context (e.g. "不是python就是js") could cause false positives. In practice this is rare because correction usually appears at sentence start.
- Only matches Chinese. English corrections like "wrong", "no", "redo" are not matched. Add English patterns if your app supports English users.
- Only checks trace-level `input`. If user corrections are in nested observation inputs, they may be missed.

### Language detection

To avoid false positives for non-Chinese text, the regex implicitly relies on Chinese character matching. English variants:

```
wrong|not right|incorrect|redo|retry|too many|too few|missing|remove|delete|start over
```

Add to an `CORRECTION_PATTERN_EN` variable and check both patterns in `detect_correction()`.
