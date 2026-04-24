"""JSON-file based dedup store for already-notified IPO codes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "seen.json"


def load(path: Path = DEFAULT_PATH) -> dict:
    if not path.exists():
        return {"notified": {}}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(state: dict, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def mark_notified(state: dict, code: str, meta: dict) -> None:
    state.setdefault("notified", {})[code] = meta


def is_notified(state: dict, code: str) -> bool:
    return code in state.get("notified", {})


def prune_stale(state: dict, valid_codes: Iterable[str]) -> None:
    """Drop entries whose code is no longer in the upcoming list.

    (Keeps the file small over time and lets a re-listed/re-priced IPO re-notify.)
    """
    valid = set(valid_codes)
    current = state.get("notified", {})
    state["notified"] = {k: v for k, v in current.items() if k in valid}
