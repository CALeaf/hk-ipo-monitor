"""Orchestrator: fetch upcoming IPOs → score on stable fields → push to Telegram.

Scoring uses only data we can reliably scrape off AAStocks (sponsor, industry,
market cap, price range). The TG message then nudges the user to personally
verify the dynamic signals (超购 / 基石 / A+H) before committing.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from . import fetcher, scorer, storage, telegram


HKT = timezone(timedelta(hours=8))
PEER_STATS_PATH = Path(__file__).resolve().parent.parent / "data" / "peer_stats.json"


def _load_peer_stats() -> dict:
    try:
        return json.loads(PEER_STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _classify_tier(text: str) -> str | None:
    """Classify an IPO into Tier1/Tier2/冷门 using the same rules as scorer."""
    if scorer._any_match(text, scorer.TIER1_INDUSTRIES): return "Tier1"
    if scorer._any_match(text, scorer.TIER2_INDUSTRIES): return "Tier2"
    if scorer._any_match(text, scorer.COLD_INDUSTRIES): return "冷门"
    return "其他"


def peer_benchmark_line(ipo: fetcher.IPO) -> str | None:
    """Return a short line like '2026 Tier2 赛道 4 只 · 均值 +87% · 胜率 100%'."""
    stats = _load_peer_stats()
    if not stats:
        return None
    text = f"{ipo.industry} {ipo.name}"
    tier = _classify_tier(text)
    if tier not in stats:
        return None
    s = stats[tier]
    return (
        f"📊 2026 同 <b>{tier}</b> 赛道历史 {s['n']} 只 · "
        f"均值 <b>{s['avg_pct']:+.1f}%</b> · "
        f"中位数 {s['median_pct']:+.1f}% · "
        f"胜率 {s['win_rate']*100:.0f}%"
    )


def _parse_aastocks_date(s: str) -> date | None:
    """'2026/04/29' → date(2026,4,29). Return None on unknown format."""
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def action_plan(ipo: fetcher.IPO) -> str:
    """Phased action plan based on where we are in the offering cycle."""
    today = datetime.now(HKT).date()
    deadline = _parse_aastocks_date(ipo.apply_deadline)
    grey = _parse_aastocks_date(ipo.grey_market_date)
    listd = _parse_aastocks_date(ipo.list_date)

    lines = ["<b>📅 行动计划：</b>"]
    if deadline and today < deadline:
        days = (deadline - today).days
        lines.append(f"  · 今天-明天（距截止 {days} 天）: 富途/捷利 查超购倍数 + 基石")
        lines.append(f"  · {deadline.strftime('%m/%d')} 14:00 前: 据下方决策表下单")
    elif deadline and today == deadline:
        lines.append(f"  · ⏰ <b>今天是申购截止日</b>（{deadline.strftime('%m/%d')}）—— 马上查超购 + 下单")
    if grey:
        lines.append(f"  · {grey.strftime('%m/%d')} 暗盘晚: 破发立即第二天开盘卖 · 涨 >20% 持有")
    if listd:
        lines.append(f"  · {listd.strftime('%m/%d')} 上市当天: 开盘直接市价卖")
    return "\n".join(lines)


DECISION_TREE = (
    "<b>🎯 超购决策表（你查到超购后照这个打）：</b>\n"
    "  · <b>&gt;100x</b> + 基石&gt;40% → 🟢 升<b>乙头</b>（辉立/耀才 100x，5 万保证金）\n"
    "  · <b>50-100x</b>            → 🟡 上<b>甲尾</b>（需 100x 杠杆，否则放弃）\n"
    "  · <b>15-50x</b>             → 🔴 <b>踩踏区间 放弃</b>（触发回拨但承接不足）\n"
    "  · <b>&lt;15x</b>             → ⚪ 1 手现金摸彩（期望值低）"
)


def build_features(ipo: fetcher.IPO) -> dict:
    """Translate scraped fields into scorer input.

    Only fields AAStocks reliably exposes. Dynamic signals (oversubscription,
    cornerstone, A+H discount) are left to the user to verify manually.
    """
    mc = None
    if ipo.market_cap_low and ipo.market_cap_high:
        mc = (ipo.market_cap_low + ipo.market_cap_high) / 2

    return {
        "sponsor": ipo.sponsor,
        "industry": ipo.industry,
        "price_range": ipo.price_range,
        "market_cap_hkd": mc,
    }


SELF_CHECK_ALWAYS = (
    "  · <b>公开超购倍数</b>（富途/捷利）—— >100x 可冲乙头；<b>15-50x 是踩踏区间，建议避开</b>\n"
    "  · <b>基石锁仓比例</b>（招股书 / 捷利港信）—— >60% 抛压小；顶级名单（淡马锡/GIC/阿布扎比/高瓴）再加一档\n"
)
SELF_CHECK_H_SHARE = (
    "  · <b>A+H 折让</b>（看当日 A 股收盘价）—— 折让 >30% 安全垫厚；港股溢价建议放弃\n"
)

# Compact rubric appended once per message — lets user learn the framework
# without needing to open the README.
SCORING_RUBRIC = (
    "<b>📏 评分手册（阈值 ≥6 乙头 / 3-5 甲尾 / 0-2 观望 / ≤-1 放弃）</b>\n"
    "  · 保荐人: 顶投 +2 / 中档 +1 / 黑名单 -3\n"
    "  · 基石: 顶级机构名单 +2 · 锁仓 >60% +2 / 40-60% +1 / <20% -1\n"
    "  · 有效流通盘 (1-基石-国配): <15% +1 / >50% -1\n"
    "  · 公开超购: >100x +4 / 50-100x +2 / <b>15-50x -3（踩踏区间）</b> / 5-15x +1 / <5x -2\n"
    "  · 赛道: Tier1(AI/大模型/半导体/创新药/储能) +2 / Tier2(软件/生物/新能源) +1 / 冷门(消费/地产/制造) -2\n"
    "  · 市值 50-500 亿 +1 / <10 亿 -1 · 定价: 下限 +1 / 上限 -1\n"
    "  · A+H 折让 >30% +2 / 15-30% +1 / 港股溢价 -1 · 机制 B +1\n"
)


def _is_h_share(ipo: fetcher.IPO) -> bool:
    """Detect dual-listed A+H stock from the IPO name suffix."""
    name = (ipo.name or "").upper()
    # AAStocks uses "─H" or "- H shares"; HKEX NLR uses "- H shares"
    return "─H" in ipo.name or "- H SHARES" in name or "H SHARES" in name


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
    lines.append(f"<b>{scorer.label(score.recommendation)}</b> (基础分 {score.total})")
    for r in score.reasons:
        lines.append(f"  {r}")

    # Peer benchmark for the stock's tier (from backtest peer_stats.json)
    peer = peer_benchmark_line(ipo)
    if peer:
        lines.append("")
        lines.append(peer)

    # Allocation suggestion — concrete HKD amounts at user's leverage
    alloc = score.allocation or {}
    if alloc.get("note"):
        lines.append("")
        lines.append(
            f"<b>💰 档位建议（本金 {scorer.CAPITAL_HKD/1e4:.0f} 万 · 杠杆 {scorer.MARGIN_LEVERAGE:.0f}x）：</b>"
        )
        lines.append(f"  {alloc['note']}")
        if alloc.get("expected_lots") and alloc["expected_lots"] != "—":
            lines.append(f"  中签预期: {alloc['expected_lots']}")

    # Phased action plan (dates + what to do each day)
    lines.append("")
    lines.append(action_plan(ipo))

    # Decision tree keyed by 超购 (the one number that flips the call)
    lines.append("")
    lines.append(DECISION_TREE)

    # Other self-check signals that don't fit the decision tree
    lines.append("")
    lines.append("<b>📋 其他自行核对：</b>")
    lines.append("  · 基石锁仓比例（招股书 / 捷利）—— >60% 抛压小；顶级名单（淡马锡/GIC/阿布扎比/高瓴）再加一档")
    if _is_h_share(ipo):
        lines.append("  · A+H 折让（当日 A 股收盘）—— 折让 >30% 安全垫厚；港股溢价建议放弃")

    lines.append("")
    lines.append(SCORING_RUBRIC.rstrip())

    lines.append(f"\n详情: {ipo.detail_url}")
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
            print(f"[monitor] {ipo.code} already notified, skipping")
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
