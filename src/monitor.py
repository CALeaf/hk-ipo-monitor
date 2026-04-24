"""Orchestrator: fetch upcoming IPOs → enrich → score → push to Telegram."""

from __future__ import annotations

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


def build_features(ipo: fetcher.IPO) -> dict:
    """Translate the (sparse) scraped fields into scorer input.

    AAStocks gives sponsor, industry, market cap, price range.
    Oversubscription / cornerstone need other sources; omit when unknown so
    scorer degrades gracefully.
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


def run(*, dry_run: bool = False) -> int:
    ipos = fetcher.list_upcoming()
    print(f"[monitor] found {len(ipos)} upcoming IPOs")
    state = storage.load()
    storage.prune_stale(state, [i.code for i in ipos])

    sent = 0
    for ipo in ipos:
        fetcher.enrich_detail(ipo)
        feat = build_features(ipo)
        score = scorer.score_ipo(feat)
        msg = format_message(ipo, score)
        print("---")
        print(msg)

        if storage.is_notified(state, ipo.code):
            print(f"[monitor] {ipo.code} already notified, skipping push")
            continue

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
