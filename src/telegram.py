"""Minimal Telegram bot sendMessage wrapper.

If the HTML-parsed send fails (e.g. message contains `<5x` which TG sees as a
malformed tag), we automatically retry as plain text after stripping HTML
tags. Better to deliver an ugly message than to silently drop it.
"""

from __future__ import annotations

import os
import re
import sys

import requests


TG_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramError(Exception):
    pass


def _strip_html(text: str) -> str:
    """Remove all <tag> wrappers and unescape common HTML entities."""
    text = re.sub(r"<[^>]+>", "", text)
    return (
        text.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
    )


def send(text: str, *, bot_token: str | None = None, chat_id: str | None = None,
         parse_mode: str = "HTML", disable_web_page_preview: bool = True) -> dict:
    bot_token = bot_token or os.environ.get("TG_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TG_CHAT_ID")
    if not bot_token or not chat_id:
        raise TelegramError("TG_BOT_TOKEN / TG_CHAT_ID not configured")

    def _post(payload: dict) -> dict:
        r = requests.post(TG_API.format(token=bot_token), json=payload, timeout=15)
        return r.json()

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    data = _post(payload)
    if data.get("ok"):
        return data

    # HTML parse error — fall back to plain text so the user still gets the
    # alert, just without bold/etc. formatting.
    err = str(data)
    if parse_mode and ("can't parse entities" in err.lower() or "parse" in err.lower()):
        print(
            f"[telegram] HTML parse failed ({err[:120]}), retrying as plain text",
            file=sys.stderr,
        )
        plain_payload = {**payload, "text": _strip_html(text)}
        plain_payload.pop("parse_mode", None)
        data2 = _post(plain_payload)
        if data2.get("ok"):
            return data2
        raise TelegramError(f"Telegram API error (plain fallback also failed): {data2}")

    raise TelegramError(f"Telegram API error: {data}")


if __name__ == "__main__":
    # Manual test: TG_BOT_TOKEN + TG_CHAT_ID must be in env
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "🧪 hk-ipo-monitor test message"
    print(send(msg))
