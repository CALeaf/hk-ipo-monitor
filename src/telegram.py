"""Minimal Telegram bot sendMessage wrapper."""

from __future__ import annotations

import os
import requests


TG_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramError(Exception):
    pass


def send(text: str, *, bot_token: str | None = None, chat_id: str | None = None,
         parse_mode: str = "HTML", disable_web_page_preview: bool = True) -> dict:
    bot_token = bot_token or os.environ.get("TG_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TG_CHAT_ID")
    if not bot_token or not chat_id:
        raise TelegramError("TG_BOT_TOKEN / TG_CHAT_ID not configured")

    r = requests.post(
        TG_API.format(token=bot_token),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        },
        timeout=15,
    )
    data = r.json()
    if not data.get("ok"):
        raise TelegramError(f"Telegram API error: {data}")
    return data


if __name__ == "__main__":
    # Manual test: TG_BOT_TOKEN + TG_CHAT_ID must be in env
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "🧪 hk-ipo-monitor test message"
    print(send(msg))
