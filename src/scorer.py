"""Rule-based scoring engine for HK IPOs.

Produces a score, a recommendation bucket, and a list of human-readable reasons.
All rules are based on publicly discussed HK IPO heuristics (sponsor quality,
cornerstone strength, oversubscription, industry, pricing, market cap).

Feature keys are tolerant of missing data — scorer degrades gracefully when
only basic fields (e.g., sponsor + market cap) are available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

TOP_SPONSORS = [
    "中金", "中国国际金融", "China International Capital",
    "摩根士丹利", "Morgan Stanley",
    "高盛", "Goldman",
    "瑞银", "UBS",
    "摩根大通", "J.P. Morgan", "JP Morgan", "JPMorgan",
    "美银", "Bank of America", "BofA",
    "花旗", "Citi", "Citigroup",
    "汇丰", "HSBC",
    "招银国际", "CMB International",
    "中信证券", "CITIC Securities", "CITIC Capital",
    "中信建投", "CITIC Securities International", "China Securities",
    "海通国际", "Haitong International",
    "平安", "Ping An of China Capital",
    "BOCI", "中银国际",
]

MID_SPONSORS = [
    "国泰君安", "Guotai Junan",
    "华泰", "Huatai",
    "广发", "GF",
    "兴业",
    "农银国际", "ABCI",
    "建银国际", "CCB International",
    "工银国际", "ICBC International",
    "民银资本",
    "光大", "Everbright",
    "德意志", "Deutsche",
    "Nomura", "野村",
]

TOP_CORNERSTONES = [
    "淡马锡", "Temasek",
    "GIC",
    "阿布扎比", "Abu Dhabi",
    "加拿大养老", "CPPIB",
    "高瓴", "Hillhouse", "HHLR",
    "红杉", "Sequoia",
    "景林", "Aspex",
    "Black Rock", "BlackRock", "贝莱德",
    "Fidelity", "富达",
    "挪威主权", "NBIM",
]

HOT_INDUSTRIES = [
    "半导体", "芯片", "硬件", "硬科技", "AI", "人工智能",
    "生物科技", "制药", "biotech", "生物",
    "新能源", "电动", "锂",
    "机器人",
    "先进", "软件",
]

COLD_INDUSTRIES = [
    "地产", "房地产",
    "传统零售", "餐饮",
    "纸业", "水泥",
]


@dataclass
class Score:
    total: int
    recommendation: str
    reasons: list[str]

    def to_dict(self) -> dict:
        return {"total": self.total, "recommendation": self.recommendation, "reasons": self.reasons}


def _any_match(haystack: str, needles: Iterable[str]) -> list[str]:
    h = haystack or ""
    return [n for n in needles if n and n in h]


def score_ipo(features: dict) -> Score:
    """Score an IPO.

    Expected feature keys (all optional; missing = neutral):
      - sponsor: str
      - industry: str
      - price_range: str            "166.6-183.2" or "24.86"
      - issue_price_position: "low"|"high"|"mid"|None
      - cornerstone_ratio: float 0..1 (share of offering size)
      - cornerstone_names: str      comma-joined names
      - oversubscription_public: float  (e.g. 180.0 means 180x)
      - market_cap_hkd: float       issue-time market cap in HKD
      - mechanism_b: bool           True if using 2025-08 mechanism B
    """
    total = 0
    reasons: list[str] = []

    # 1. Sponsor
    sponsor = features.get("sponsor") or ""
    if sponsor:
        tops = _any_match(sponsor, TOP_SPONSORS)
        mids = _any_match(sponsor, MID_SPONSORS)
        if tops:
            total += 2
            reasons.append(f"✅ 顶级保荐: {', '.join(tops[:3])} (+2)")
        elif mids:
            total += 1
            reasons.append(f"🟡 中档保荐: {', '.join(mids[:3])} (+1)")
        else:
            reasons.append(f"⚪ 保荐: {sponsor[:40]} (0)")

    # 2. Cornerstone ratio
    cs_ratio = features.get("cornerstone_ratio")
    if cs_ratio is not None:
        if cs_ratio >= 0.60:
            total += 2
            reasons.append(f"✅ 基石占比 {cs_ratio:.0%} >=60% (+2)")
        elif cs_ratio >= 0.40:
            total += 1
            reasons.append(f"🟡 基石占比 {cs_ratio:.0%} (+1)")
        elif cs_ratio < 0.20:
            total -= 1
            reasons.append(f"❌ 基石占比 {cs_ratio:.0%} <20% (-1)")

    # 3. Cornerstone quality
    cs_names = features.get("cornerstone_names") or ""
    if cs_names:
        top_cs = _any_match(cs_names, TOP_CORNERSTONES)
        if top_cs:
            total += 2
            reasons.append(f"✅ 顶级基石: {', '.join(top_cs[:3])} (+2)")

    # 4. Oversubscription
    os_ratio = features.get("oversubscription_public")
    if os_ratio is not None:
        if os_ratio >= 100:
            total += 3
            reasons.append(f"🔥 公开超购 {os_ratio:.0f}x >=100x (+3)")
        elif os_ratio >= 20:
            total += 2
            reasons.append(f"✅ 公开超购 {os_ratio:.0f}x (+2)")
        elif os_ratio >= 5:
            total += 1
            reasons.append(f"🟡 公开超购 {os_ratio:.1f}x (+1)")
        elif os_ratio < 2:
            total -= 2
            reasons.append(f"❌ 公开超购仅 {os_ratio:.1f}x <2x，大概率破发 (-2)")

    # 5. Price position
    pos = features.get("issue_price_position")
    if pos == "low":
        total += 1
        reasons.append("✅ 下限定价 (+1)")
    elif pos == "high":
        total -= 1
        reasons.append("⚠️ 上限定价 (-1)")

    # 6. Market cap (HKD)
    mc = features.get("market_cap_hkd")
    if mc is not None:
        b = mc / 1e8  # in 亿 HKD
        if 50 <= b <= 500:
            total += 1
            reasons.append(f"✅ 发行市值 {b:.0f} 亿，甜点区间 (+1)")
        elif b < 10:
            total -= 1
            reasons.append(f"❌ 发行市值 {b:.1f} 亿，偏小 (-1)")
        elif b > 1000:
            reasons.append(f"⚪ 发行市值 {b:.0f} 亿，巨无霸 (0)")

    # 7. Industry
    ind = features.get("industry") or ""
    if ind:
        hot = _any_match(ind, HOT_INDUSTRIES)
        cold = _any_match(ind, COLD_INDUSTRIES)
        if hot:
            total += 1
            reasons.append(f"✅ 热门赛道: {ind} (+1)")
        elif cold:
            total -= 1
            reasons.append(f"❌ 冷门行业: {ind} (-1)")

    # 8. Mechanism B (2025-08 new rule)
    if features.get("mechanism_b"):
        total += 1
        reasons.append("✅ 采用机制B发行 (+1)")

    rec = _recommendation(total)
    return Score(total=total, recommendation=rec, reasons=reasons)


def _recommendation(score: int) -> str:
    if score >= 7:
        return "STRONG_BUY_MARGIN_YIHEAD"   # 强推 · 融资打乙头
    if score >= 4:
        return "BUY_ONE_LOT"                 # 1 手现金
    if score >= 1:
        return "WATCH"                       # 观望
    return "SKIP"                            # 放弃


RECOMMENDATION_LABELS = {
    "STRONG_BUY_MARGIN_YIHEAD": "🟢 强推 · 融资打乙头",
    "BUY_ONE_LOT":              "🟡 1 手现金申购",
    "WATCH":                    "⚪ 观望 / 看暗盘",
    "SKIP":                     "🔴 放弃",
}


def label(rec: str) -> str:
    return RECOMMENDATION_LABELS.get(rec, rec)


if __name__ == "__main__":
    # Manual smoke test with a rich feature set
    demo = {
        "sponsor": "中国国际金融香港证券有限公司、海通国际资本有限公司",
        "industry": "先进硬件及软件",
        "cornerstone_ratio": 0.65,
        "cornerstone_names": "GIC, Aspex, 高瓴",
        "oversubscription_public": 180,
        "issue_price_position": "high",
        "market_cap_hkd": 180e8,
        "mechanism_b": True,
    }
    s = score_ipo(demo)
    print(f"score: {s.total}  rec: {label(s.recommendation)}")
    for r in s.reasons:
        print(" ", r)
