# Feishu Card Message Format

Reference: https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-components

## Message structure

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "📊 Langfuse 日报 | 2026-05-06"
      },
      "template": "blue"
    },
    "elements": [
      {
        "tag": "markdown",
        "content": "text with **markdown** formatting"
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "multiline markdown"
        }
      },
      {
        "tag": "hr"
      }
    ]
  }
}
```

## Component types used

| Tag | Use |
|-----|-----|
| `markdown` | Simple single-line labels |
| `div` + `lark_md` | Multi-line markdown blocks (supports `**bold**`, lists, links) |
| `hr` | Horizontal divider between sections |

## Content size limits

- Total card: ~30KB JSON
- Single element content: ~4KB
- So `scripts/report.py` truncates long sections to 3000 chars for lark_md blocks

## Testing

Send a test card with curl:

```bash
curl -X POST "$FEISHU_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "interactive",
    "card": {
      "header": {
        "title": {"tag": "plain_text", "content": "Test Card"},
        "template": "blue"
      },
      "elements": [
        {"tag": "div", "text": {"tag": "lark_md", "content": "**Test** message from langfuse-insight"}}
      ]
    }
  }'
```

## Webhook setup

1. Create a Feishu group chat
2. Add "Custom Bot" -> "Add Robot" -> "Add Webhook"
3. Copy the webhook URL: `https://open.feishu.cn/open-apis/bot/v2/hook/xxx`
4. Set `FEISHU_WEBHOOK` environment variable
