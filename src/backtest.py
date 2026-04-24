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

from . import scorer


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


def score_from_nlr(row: IPORow) -> scorer.Score:
    """Feed only the NLR-available features into scorer.

    NLR has sponsor + issue price. Industry / cornerstone / oversubscription
    are unknown at backtest time unless enriched separately.
    """
    return scorer.score_ipo({
        "sponsor": row.sponsor,
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
        s = score_from_nlr(ipo)
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
        })
        time.sleep(0.3)  # polite to yahoo

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
    c = cum_per_share([r for r in valid if r["rec"] == "STRONG_BUY_MARGIN_YIHEAD"])
    d = cum_per_share([r for r in valid if r["score"] >= 2])  # top-sponsor proxy

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
    lines.append(f"| B · 筛选 (非 SKIP) 1 手 | {b['n']} | {b['win_rate']:.0%} | {b['avg_pct']:+.2f}% | {b['total_pct']:+.2f}% |")
    lines.append(f"| C · 强推 (score≥7) 1 手 | {c['n']} | {c['win_rate']:.0%} | {c['avg_pct']:+.2f}% | {c['total_pct']:+.2f}% |")
    lines.append(f"| D · 仅顶级保荐 (score≥2) 1 手 | {d['n']} | {d['win_rate']:.0%} | {d['avg_pct']:+.2f}% | {d['total_pct']:+.2f}% |")
    lines.append("")
    lines.append("> ⚠️ 回测输入仅含 HKEX NLR 公开字段（代码、发行价、上市日期、保荐人）。")
    lines.append("> 基石强度/超购倍数在回测时点无法还原，因此 B/C 策略以保荐人质量为主，")
    lines.append("> 实盘 Monitor 会多维度打分（见 scorer.py）。")
    lines.append("")
    if a["best"]:
        lines.append(f"最佳: {a['best']['code']} {a['best']['name'][:20]} {a['best']['pct']:+.2f}%")
    if a["worst"]:
        lines.append(f"最差: {a['worst']['code']} {a['worst']['name'][:20]} {a['worst']['pct']:+.2f}%")

    lines.append("\n## 明细\n")
    lines.append("| 代码 | 名称 | 上市日 | 招股价 | 首日开盘 | 涨跌% | 分数 | 建议 | 保荐 |")
    lines.append("|---|---|---|---:|---:|---:|---:|---|---|")
    for r in sorted(rows, key=lambda x: x["list_date"]):
        fo = f"{r['first_day_open']:.3f}" if r["first_day_open"] else "—"
        pct = f"{r['pct']:+.2f}%" if r["pct"] is not None else "—"
        sponsor = (r["sponsor"] or "")[:40]
        name = (r["name"] or "")[:30]
        lines.append(
            f"| {r['code']} | {name} | {r['list_date']} | {r['issue_price']:.3f} | "
            f"{fo} | {pct} | {r['score']} | {scorer.label(r['rec'])} | {sponsor} |"
        )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[backtest] wrote {REPORT_PATH}")
    return {"report": str(REPORT_PATH), "n": len(rows), "A": a, "B": b, "C": c, "D": d}


if __name__ == "__main__":
    result = run()
    print(f"\n=== summary ===")
    for k in ("A", "B", "C", "D"):
        s = result[k]
        print(f"  {k}: n={s['n']} win={s['win_rate']:.0%} avg={s['avg_pct']:+.2f}% total={s['total_pct']:+.2f}%")
