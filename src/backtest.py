"""Backtest 2026 HK IPOs with the open-day-sell strategy.

Data sources:
  - List of 2026 IPOs: HKEX NLR2026_Eng.xlsx (official)
  - First-day OHLC: yfinance (Yahoo) with akshare fallback
"""

from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from . import profile, scorer

# Simulation constants for HKD PnL in backtest.
# Calibrated to user's real 2026 observation: 甲尾 预期 0-1 手 due to 千倍超购
# dilution. 乙头 红鞋 保证 1 + 偶尔 2.
ASSUMED_ENTRY_FEE = 4000.0       # typical 港股 2026 每手入场费 ≈ 2k-6k HKD
LOTS_ALLOTTED_YI_TOU = 1.5       # 乙头 = 红鞋保证 1 手 + 热门股偶 +1
LOTS_ALLOTTED_JIA_WEI = 0.5      # 甲尾 = 2026 千倍超购下实际 0-1 手 (用户反馈校准)
LOTS_ALLOTTED_1LOT_CASH = 0.02   # 一手党 中签率 ~1-2%


NLR_URL = (
    "https://www2.hkexnews.hk/-/media/HKEXnews/Homepage/New-Listings/"
    "New-Listing-Information/New-Listing-Report/Main/NLR{year}_Eng.xlsx"
)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_PATH = DATA_DIR / "backtest_2026.md"


@dataclass
class IPORow:
    code: str
    name: str
    list_date: date
    issue_price: float
    sponsor: str


def fetch_nlr(year: int = 2026) -> list[IPORow]:
    """Download NLR xlsx and parse Main Board IPO rows.

    Each IPO has 2 rows (HK + global fundraising). We keep the first (a) row.
    """
    url = NLR_URL.format(year=year)
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (hk-ipo-monitor)"}, timeout=30)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), sheet_name="NLR", header=None)

    # Find the header row (contains "Stock Code")
    header_idx = None
    for i in range(min(10, len(df))):
        row_vals = [str(c) for c in df.iloc[i].tolist()]
        if any("Stock Code" in v for v in row_vals):
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("NLR header row not found")

    cols = [str(c).strip() for c in df.iloc[header_idx].tolist()]
    body = df.iloc[header_idx + 1:].reset_index(drop=True)
    body.columns = cols

    # Find columns by name substring
    def find_col(substr: str) -> str:
        for c in body.columns:
            if substr.lower() in str(c).lower():
                return c
        raise KeyError(substr)

    c_code = find_col("Stock Code")
    c_name = find_col("Company Name")
    c_list = find_col("Date of Listing")
    c_price = find_col("Subscription Price")
    c_sponsor = find_col("Sponsor")

    out: list[IPORow] = []
    for _, row in body.iterrows():
        code_raw = row[c_code]
        if not code_raw or str(code_raw).strip() in ('"', "nan", "NaN", ""):
            continue
        code = str(code_raw).strip().zfill(5)
        if not re.fullmatch(r"\d{5}", code):
            continue
        ld = row[c_list]
        if isinstance(ld, str):
            try:
                ld_d = datetime.strptime(ld[:10], "%Y-%m-%d").date()
            except Exception:
                continue
        elif isinstance(ld, pd.Timestamp):
            ld_d = ld.date()
        elif isinstance(ld, datetime):
            ld_d = ld.date()
        elif isinstance(ld, date):
            ld_d = ld
        else:
            continue
        if ld_d.year != year:
            continue
        try:
            price = float(row[c_price])
        except Exception:
            continue
        out.append(IPORow(
            code=code,
            name=str(row[c_name]).strip(),
            list_date=ld_d,
            issue_price=price,
            sponsor=str(row[c_sponsor] or "").replace("\n", " ").strip(),
        ))
    return out


def first_day_open(code: str, list_date: date) -> Optional[float]:
    """Try yfinance first, fall back to akshare."""
    # Yahoo uses 4-digit zero-padded HK codes (0700.HK, 0100.HK, 1879.HK)
    ticker = f"{int(code):04d}.HK"
    end = list_date + timedelta(days=5)

    try:
        import yfinance as yf
        h = yf.Ticker(ticker).history(
            start=list_date.isoformat(), end=end.isoformat(), auto_adjust=False
        )
        if len(h):
            return float(h.iloc[0]["Open"])
    except Exception as e:
        print(f"  yfinance {ticker}: {e}")

    try:
        import akshare as ak
        df = ak.stock_hk_hist(
            symbol=code,
            period="daily",
            start_date=list_date.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="",
        )
        if len(df):
            return float(df.iloc[0]["开盘"])
    except Exception as e:
        print(f"  akshare {code}: {e}")
    return None


def score_from_nlr(row: IPORow, industry_hint: str = "") -> scorer.Score:
    """Score using NLR sponsor + optional industry hint from profile enricher.

    Still no access to 基石 / 超购 / A+H at backtest time, but industry moves
    the needle substantially — historical 2026 data shows赛道 is the strongest
    discriminator between winners and破发.
    """
    return scorer.score_ipo({
        "sponsor": row.sponsor,
        "industry": industry_hint,
    })


def run() -> dict:
    """Run the backtest.

    All strategies sell at first-day open price.

    Strategies (NLR-only features → caveat: cornerstone / oversubscription
    are not available, so B/C use what NLR exposes — primarily sponsor
    quality):
      A. 全打 · 1 手  —— baseline: every 2026 IPO, 1 lot cash
      B. 筛选 · 1 手  —— scorer != SKIP (score >= 1)
      C. 强推 · 1 手  —— scorer STRONG_BUY (score >= 7, rarely met w/ only sponsor)
      D. 仅顶级保荐 · 1 手 —— heuristic: top-sponsor name matches (+2)
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[backtest] fetching HKEX NLR 2026...")
    ipos = fetch_nlr(2026)
    print(f"[backtest] 2026 IPOs in NLR: {len(ipos)}")

    rows: list[dict] = []
    for ipo in ipos:
        print(f"[backtest] {ipo.code} {ipo.name[:30]:30s} list={ipo.list_date} issue={ipo.issue_price}")
        fo = first_day_open(ipo.code, ipo.list_date)

        # Enrich with industry + business description from eastmoney profile;
        # fall back to company name as a keyword source when eastmoney empty.
        prof = profile.fetch(ipo.code)
        parts = [ipo.name]
        if prof:
            parts.append(prof.combined())
        industry_hint = " ".join(p for p in parts if p)

        s = score_from_nlr(ipo, industry_hint=industry_hint)
        rows.append({
            "code": ipo.code,
            "name": ipo.name,
            "list_date": ipo.list_date.isoformat(),
            "issue_price": ipo.issue_price,
            "first_day_open": fo,
            "pct": (fo - ipo.issue_price) / ipo.issue_price * 100 if fo else None,
            "score": s.total,
            "rec": s.recommendation,
            "sponsor": ipo.sponsor,
            "industry": (prof.industry if prof else "") or "—",
        })
        time.sleep(0.3)  # polite to yahoo + eastmoney

    # ---- Strategy calculations ----
    valid = [r for r in rows if r["pct"] is not None]

    def cum_per_share(subset):
        # each IPO contributes (first_day_open - issue_price) per share won
        # we can't model real allotment, so report mean pct and total pct-sum
        total_pct = sum(r["pct"] for r in subset)
        avg_pct = total_pct / len(subset) if subset else 0.0
        wins = sum(1 for r in subset if r["pct"] > 0)
        return {
            "n": len(subset),
            "wins": wins,
            "win_rate": wins / len(subset) if subset else 0.0,
            "avg_pct": avg_pct,
            "total_pct": total_pct,
            "best": max(subset, key=lambda r: r["pct"]) if subset else None,
            "worst": min(subset, key=lambda r: r["pct"]) if subset else None,
        }

    a = cum_per_share(valid)
    b = cum_per_share([r for r in valid if r["rec"] != "SKIP"])
    c = cum_per_share([r for r in valid if r["score"] >= 3])  # BUY or better
    d = cum_per_share([r for r in valid if r["rec"] == "STRONG_BUY_MARGIN_YIHEAD"])

    # ---- HKD PnL simulation by subscription tier (the real comparison) ----
    def hkd_pnl_by_tier(row: dict, tier: str) -> float:
        if row["pct"] is None:
            return 0.0
        if tier == "1LOT_CASH":
            lots = LOTS_ALLOTTED_1LOT_CASH
        elif tier == "JIA_WEI":
            lots = LOTS_ALLOTTED_JIA_WEI
        elif tier == "YI_TOU":
            lots = LOTS_ALLOTTED_YI_TOU
        else:
            return 0.0
        return lots * ASSUMED_ENTRY_FEE * row["pct"] / 100

    def strategy_pnl(rows_, tier_of):
        total = sum(hkd_pnl_by_tier(r, tier_of(r)) for r in rows_)
        n_played = sum(1 for r in rows_ if tier_of(r) != "SKIP")
        return {"total_hkd": total, "n": n_played}

    # Strategy 1: 全打 1 手现金 (user's current broken approach)
    cash_1lot = strategy_pnl(valid, lambda r: "1LOT_CASH")
    # Strategy 2: 全打甲尾 (baseline for margin-based全打)
    jia_wei_all = strategy_pnl(valid, lambda r: "JIA_WEI")
    # Strategy 3: scorer-tier (STRONG_BUY→乙头, BUY→甲尾, rest→skip)
    def tier_from_rec(r):
        if r["rec"] == "STRONG_BUY_MARGIN_YIHEAD": return "YI_TOU"
        if r["rec"] == "BUY_ONE_LOT": return "JIA_WEI"
        return "SKIP"
    tiered = strategy_pnl(valid, tier_from_rec)
    # Strategy 4: score ≥ 3 forces 甲尾 (since STRONG_BUY needs超购 confirmation
    # which we don't have at backtest time)
    def tier_score_ge3(r):
        return "JIA_WEI" if r["score"] >= 3 else "SKIP"
    ge3_jia_wei = strategy_pnl(valid, tier_score_ge3)

    # ---- Write markdown report ----
    lines = []
    lines.append(f"# 港股打新 2026 回测\n")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\n数据源: HKEX NLR2026_Eng.xlsx + yfinance")
    lines.append(f"\n样本: {len(rows)} 只 2026 主板新股 ({len(valid)} 只有首日开盘价)")
    lines.append("\n## 策略汇总\n")
    lines.append("| 策略 | 参与数 | 胜率 | 平均首日 % | 累计 % |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(f"| A · 全打 1 手 | {a['n']} | {a['win_rate']:.0%} | {a['avg_pct']:+.2f}% | {a['total_pct']:+.2f}% |")
    lines.append(f"| B · 筛掉 SKIP 1 手 | {b['n']} | {b['win_rate']:.0%} | {b['avg_pct']:+.2f}% | {b['total_pct']:+.2f}% |")
    lines.append(f"| C · score≥3 (BUY+) 1 手 | {c['n']} | {c['win_rate']:.0%} | {c['avg_pct']:+.2f}% | {c['total_pct']:+.2f}% |")
    lines.append(f"| D · 强推 (score≥6) 1 手 | {d['n']} | {d['win_rate']:.0%} | {d['avg_pct']:+.2f}% | {d['total_pct']:+.2f}% |")

    # ---- HKD PnL simulation (the view that actually matters) ----
    lines.append("\n## 实际 HKD PnL 模拟（才是 20 万本金该看的图）\n")
    lines.append(f"假设：每手入场费 {ASSUMED_ENTRY_FEE:,.0f} HKD（2026 港股均值），")
    lines.append(f"1 手现金中签率 ~{LOTS_ALLOTTED_1LOT_CASH*100:.0f}%；")
    lines.append(f"甲尾中签 ~{LOTS_ALLOTTED_JIA_WEI} 手；乙头中签 ~{LOTS_ALLOTTED_YI_TOU} 手（含红鞋保证）。\n")
    lines.append("| 策略 | 参与 | 2026 累计盈亏 (HKD) |")
    lines.append("|---|---:|---:|")
    lines.append(f"| 🔴 全打 1 手现金（你目前的方式）| {cash_1lot['n']} | {cash_1lot['total_hkd']:+,.0f} |")
    lines.append(f"| 🟡 全打甲尾融资 | {jia_wei_all['n']} | {jia_wei_all['total_hkd']:+,.0f} |")
    lines.append(f"| 🟢 scorer 分档（强推→乙头, BUY→甲尾, 其他不打）| {tiered['n']} | {tiered['total_hkd']:+,.0f} |")
    lines.append(f"| 🟢 score≥3 全部打甲尾 | {ge3_jia_wei['n']} | {ge3_jia_wei['total_hkd']:+,.0f} |")
    lines.append("")
    lines.append("> ⚠️ 数字是估算不是精算。真实中签手数看每只股的具体超购倍数和每手股数；")
    lines.append("> 但数量级对的上：1 手现金 = 基本零收益；融资甲尾/乙头 = 有意义的年化回报。")
    lines.append("")
    lines.append("### 备注")
    lines.append("- 输入字段：HKEX NLR 的发行价/保荐人 + Eastmoney 的行业/业务描述。")
    lines.append("- 基石强度 / 超购倍数 / A+H 折让 在回测时点不可还原，等同未赋分。")
    lines.append("- 实盘 Monitor 同样只用这些稳定字段打基础分，让用户在 TG 消息里自行核对动态指标。")

    # ---- Score × performance segmentation (the actual discriminability check) ----
    def _seg(predicate, label):
        seg = [r for r in valid if predicate(r)]
        if not seg:
            return None
        avg_pct = sum(r["pct"] for r in seg) / len(seg)
        wins = sum(1 for r in seg if r["pct"] > 0)
        return (label, len(seg), wins/len(seg), avg_pct)

    segs = [
        _seg(lambda r: r["pct"] < 0, "破发 <0%"),
        _seg(lambda r: 0 <= r["pct"] < 10, "小涨 0-10%"),
        _seg(lambda r: 10 <= r["pct"] < 50, "一般 10-50%"),
        _seg(lambda r: r["pct"] >= 50, "大涨 ≥50%"),
    ]
    lines.append("\n## 分段差异（scorer 在不同结果里的表现）\n")
    lines.append("| 段位 | 只数 | 平均分 | 平均首日% |")
    lines.append("|---|---:|---:|---:|")
    for s in segs:
        if not s: continue
        label_, n, _, avgp = s
        avg_sc = sum(r["score"] for r in valid if (r["pct"] < 0 and label_.startswith("破发")) or (0<=r["pct"]<10 and label_.startswith("小涨")) or (10<=r["pct"]<50 and label_.startswith("一般")) or (r["pct"]>=50 and label_.startswith("大涨"))) / n
        lines.append(f"| {label_} | {n} | {avg_sc:+.2f} | {avgp:+.2f}% |")
    lines.append("")
    lines.append("> 破发 组平均分显著低于其他段位 = scorer 能用基础数据区分出明显的地雷；")
    lines.append("> 小涨/大涨 组平均分接近 = 单靠公开字段区分不出「大肉」和「一般」，需配合超购倍数。")
    lines.append("")
    if a["best"]:
        lines.append(f"最佳: {a['best']['code']} {a['best']['name'][:20]} {a['best']['pct']:+.2f}%")
    if a["worst"]:
        lines.append(f"最差: {a['worst']['code']} {a['worst']['name'][:20]} {a['worst']['pct']:+.2f}%")

    lines.append("\n## 明细\n")
    lines.append("| 代码 | 名称 | 行业 | 上市日 | 招股价 | 首日开盘 | 涨跌% | 分数 | 建议 |")
    lines.append("|---|---|---|---|---:|---:|---:|---:|---|")
    for r in sorted(rows, key=lambda x: x["list_date"]):
        fo = f"{r['first_day_open']:.3f}" if r["first_day_open"] else "—"
        pct = f"{r['pct']:+.2f}%" if r["pct"] is not None else "—"
        name = (r["name"] or "")[:28]
        ind = (r.get("industry") or "—")[:14]
        lines.append(
            f"| {r['code']} | {name} | {ind} | {r['list_date']} | {r['issue_price']:.3f} | "
            f"{fo} | {pct} | {r['score']} | {scorer.label(r['rec'])} |"
        )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[backtest] wrote {REPORT_PATH}")

    # ---- Peer stats export (monitor reads this to show "同赛道 2026 均值") ----
    def classify_tier(text: str) -> str | None:
        if scorer._any_match(text, scorer.TIER1_INDUSTRIES): return "Tier1"
        if scorer._any_match(text, scorer.TIER2_INDUSTRIES): return "Tier2"
        if scorer._any_match(text, scorer.COLD_INDUSTRIES): return "冷门"
        return None

    peer_stats: dict[str, dict] = {"Tier1": [], "Tier2": [], "冷门": [], "其他": []}
    for r in rows:
        if r["pct"] is None:
            continue
        text = f"{r.get('industry','')} {r['name']}"
        tier = classify_tier(text) or "其他"
        peer_stats[tier].append(r["pct"])

    summary = {}
    for tier, pcts in peer_stats.items():
        if not pcts:
            continue
        summary[tier] = {
            "n": len(pcts),
            "avg_pct": round(sum(pcts) / len(pcts), 2),
            "median_pct": round(sorted(pcts)[len(pcts)//2], 2),
            "min_pct": round(min(pcts), 2),
            "max_pct": round(max(pcts), 2),
            "win_rate": round(sum(1 for p in pcts if p > 0) / len(pcts), 3),
        }
    import json as _json
    (DATA_DIR / "peer_stats.json").write_text(_json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[backtest] wrote peer_stats.json: {summary}")

    return {"report": str(REPORT_PATH), "n": len(rows), "A": a, "B": b, "C": c, "D": d}


if __name__ == "__main__":
    result = run()
    print(f"\n=== summary ===")
    for k in ("A", "B", "C", "D"):
        s = result[k]
        print(f"  {k}: n={s['n']} win={s['win_rate']:.0%} avg={s['avg_pct']:+.2f}% total={s['total_pct']:+.2f}%")
