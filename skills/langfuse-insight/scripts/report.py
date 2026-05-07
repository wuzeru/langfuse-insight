#!/usr/bin/env python3
"""Push Langfuse insight reports to various channels.

Usage:
  python3 report.py insight_2026-05-06.md
  python3 report.py insight_2026-05-06.md --feishu $FEISHU_WEBHOOK
  python3 report.py insight_2026-05-06.md --slack $SLACK_WEBHOOK
  python3 report.py insight_2026-05-06.md --save-to reports/
"""

import argparse
import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_report(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_sections(md: str) -> dict[str, str]:
    """Extract ## sections from markdown."""
    sections = {}
    current_title = None
    current_lines = []

    for line in md.splitlines():
        if line.startswith("## "):
            if current_title:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = line[3:].strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)
    if current_title:
        sections[current_title] = "\n".join(current_lines).strip()

    return sections


# ---------------------------------------------------------------------------
# Feishu card message
# ---------------------------------------------------------------------------

def build_feishu_card(md: str, title: str) -> dict:
    """Build a Feishu interactive card from markdown content.

    Reference: Feishu Message Card Template Builder
    https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-components
    """
    sections = extract_sections(md)
    elements = []

    elements.append({
        "tag": "markdown",
        "content": f"**📊 {title}**\n",
    })

    summary = sections.get("基础统计", "")
    if summary:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": summary.strip().replace("\n", "\n\n"),
            },
        })

    pain = sections.get("Top 3 卡点", "") or sections.get("卡点分析", "")
    if pain:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": "**🔴 卡点分析**",
        })
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": pain.strip()[:3000],
            },
        })

    suggestions = sections.get("修复建议", "") or sections.get("改进建议", "")
    if suggestions:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": "**💡 改进建议**",
        })
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": suggestions.strip()[:3000],
            },
        })

    trend = sections.get("趋势对比", "") or sections.get("趋势", "")
    if trend:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"📈 **趋势**\n{trend.strip()[:1000]}",
            },
        })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": "blue",
            },
            "elements": elements,
        },
    }


def send_feishu(webhook: str, card: dict, timeout: int = 30) -> bool:
    try:
        import httpx
    except ImportError:
        print("[warn] httpx not installed. Install with: pip install httpx")
        return False

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(webhook, json=card)
            if resp.status_code == 200:
                print("[feishu] sent successfully")
                return True
            print(f"[feishu] HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as exc:
        print(f"[feishu] error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Slack Block Kit
# ---------------------------------------------------------------------------

def build_slack_blocks(md: str, title: str) -> list[dict]:
    """Build Slack Block Kit message from markdown content."""
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f":bar_chart: {title}"},
        },
        {
            "type": "divider",
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": md[:3000]},
        },
    ]


def send_slack(webhook: str, blocks: list[dict], timeout: int = 30) -> bool:
    try:
        import httpx
    except ImportError:
        print("[warn] httpx not installed.")
        return False

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(webhook, json={"blocks": blocks})
            if resp.status_code == 200:
                print("[slack] sent successfully")
                return True
            print(f"[slack] HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as exc:
        print(f"[slack] error: {exc}")
        return False


# ---------------------------------------------------------------------------
# File / stdout
# ---------------------------------------------------------------------------

def save_markdown(md: str, output_dir: str, source_path: str) -> str:
    """Save report markdown to output directory."""
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(source_path)
    dest = os.path.join(output_dir, filename)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[file] saved to {dest}")
    return dest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Push Langfuse insight report to various channels"
    )
    parser.add_argument("report", help="Path to insight markdown file")
    parser.add_argument("--feishu", default=None, help="Feishu webhook URL")
    parser.add_argument("--slack", default=None, help="Slack webhook URL")
    parser.add_argument("--save-to", default=None, help="Save to directory")
    parser.add_argument(
        "--title", default=None, help="Report title (default: derived from filename)"
    )
    args = parser.parse_args()

    md = load_report(args.report)

    basename = os.path.splitext(os.path.basename(args.report))[0]
    if args.title:
        title = args.title
    else:
        date_str = basename.replace("insight_", "").replace("insight-", "")
        title = f"Langfuse 日报 | {date_str}"

    sent_anywhere = False

    feishu_webhook = args.feishu or os.environ.get("FEISHU_WEBHOOK")
    if feishu_webhook:
        card = build_feishu_card(md, title)
        if send_feishu(feishu_webhook, card):
            sent_anywhere = True

    slack_webhook = args.slack or os.environ.get("SLACK_WEBHOOK")
    if slack_webhook:
        blocks = build_slack_blocks(md, title)
        if send_slack(slack_webhook, blocks):
            sent_anywhere = True

    if args.save_to:
        save_markdown(md, args.save_to, args.report)
        sent_anywhere = True

    if not sent_anywhere:
        print(md)


if __name__ == "__main__":
    main()
