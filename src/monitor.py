"""Orchestrator: fetch upcoming IPOs → enrich → score → push to Telegram."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from . import fetcher, scorer, storage, telegram


HKT = timezone(timedelta(hours=8))
OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "data" / "overrides.json"


def load_overrides() -> dict:
    """Load per-code feature overrides (oversubscription / cornerstone / A+H etc.)."""
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        with OVERRIDES_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        print(f"[monitor] overrides load failed: {e}", file=sys.stderr)
        return {}


def build_features(ipo: fetcher.IPO, overrides: dict | None = None) -> dict:
    """Translate scraped fields + user overrides into scorer input.

    AAStocks gives sponsor / industry / market cap / price range automatically.
    Real-time fields (oversubscription, cornerstone, A+H discount) come from
    data/overrides.json — the user fills them in from 富途 / 捷利 / prospectus.
    """
    mc = None
    if ipo.market_cap_low and ipo.market_cap_high:
        mc = (ipo.market_cap_low + ipo.market_cap_high) / 2

    feat = {
        "sponsor": ipo.sponsor,
        "industry": ipo.industry,
        "price_range": ipo.price_range,
        "market_cap_hkd": mc,
    }

    if overrides and ipo.code in overrides:
        feat.update(overrides[ipo.code])
    return feat


def format_message(ipo: fetcher.IPO, score: scorer.Score) -> str:
    """HTML-formatted Telegram message for one IPO."""
    lines = []
    lines.append(f"🔔 <b>港股新股</b> · {datetime.now(HKT).strftime('%Y-%m-%d %H:%M HKT')}")
    lines.append("")
    lines.append(f"📌 <b>{ipo.name}</b> ({ipo.code}.HK)")
    if ipo.industry:
        lines.append(f"行业: {ipo.industry}")
    if ipo.price_range:
        lot = f"/ 手 {ipo.lot_size} 股" if ipo.lot_size else ""
        lines.append(f"招股价: {ipo.price_range} HKD {lot}")
    if ipo.entry_fee:
        lines.append(f"入场费: {ipo.entry_fee:,.0f} HKD")
    if ipo.market_cap_low and ipo.market_cap_high:
        lo = ipo.market_cap_low / 1e8
        hi = ipo.market_cap_high / 1e8
        if abs(hi - lo) < 0.01:
            lines.append(f"市值: {lo:.1f} 亿 HKD")
        else:
            lines.append(f"市值: {lo:.1f}–{hi:.1f} 亿 HKD")
    if ipo.apply_deadline:
        lines.append(f"申购截止: {ipo.apply_deadline}")
    if ipo.list_date:
        lines.append(f"上市: {ipo.list_date}")
    if ipo.sponsor:
        lines.append(f"保荐: {ipo.sponsor[:80]}")

    lines.append("")
    lines.append(f"<b>{scorer.label(score.recommendation)}</b> (score {score.total})")
    for r in score.reasons:
        lines.append(f"  {r}")
    lines.append("")
    lines.append(f"详情: {ipo.detail_url}")
    return "\n".join(lines)


def _should_resend(prev: dict, new_score: scorer.Score) -> bool:
    """Re-send if recommendation bucket changed or score moved by ≥2 points.

    This matters because 超购倍数 / 基石 become known late in the offering cycle
    and can flip a 'WATCH' into 'STRONG_BUY' or a 'BUY' into 'SKIP'.
    """
    if prev.get("recommendation") != new_score.recommendation:
        return True
    if abs(int(prev.get("score", 0)) - int(new_score.total)) >= 2:
        return True
    return False


def run(*, dry_run: bool = False) -> int:
    ipos = fetcher.list_upcoming()
    print(f"[monitor] found {len(ipos)} upcoming IPOs")
    overrides = load_overrides()
    if overrides:
        print(f"[monitor] loaded overrides for {len(overrides)} codes: {list(overrides)}")

    state = storage.load()
    storage.prune_stale(state, [i.code for i in ipos])

    sent = 0
    for ipo in ipos:
        fetcher.enrich_detail(ipo)
        feat = build_features(ipo, overrides)
        score = scorer.score_ipo(feat)
        msg = format_message(ipo, score)
        print("---")
        print(msg)

        prev = state.get("notified", {}).get(ipo.code)
        if prev and not _should_resend(prev, score):
            print(f"[monitor] {ipo.code} already notified (score unchanged), skipping push")
            continue
        if prev:
            print(f"[monitor] {ipo.code} score changed ({prev.get('score')}→{score.total}), re-pushing")

        if dry_run:
            print("[monitor] dry-run, not sending")
        else:
            try:
                telegram.send(msg)
                sent += 1
                storage.mark_notified(state, ipo.code, {
                    "name": ipo.name,
                    "list_date": ipo.list_date,
                    "recommendation": score.recommendation,
                    "score": score.total,
                    "notified_at": datetime.now(HKT).isoformat(timespec="seconds"),
                })
            except telegram.TelegramError as e:
                print(f"[monitor] TG send failed for {ipo.code}: {e}", file=sys.stderr)

    storage.save(state)
    print(f"[monitor] done. sent={sent}, total={len(ipos)}")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(run(dry_run=dry))
