"""Rule-based scoring engine for HK IPOs.

Scoring philosophy follows the "open-day flip" school: we're paying for
liquidity + sentiment premium on day 1, not holding long term.

Dimensions (all optional; missing data = neutral):
  - Sponsor quality (顶级 / 中档 / 黑名单)
  - Cornerstone ratio (锁仓比例) and quality (基石质量)
  - Public oversubscription — note the 15-50x "dead zone" that historically
    triggers the 30% callback without enough demand to absorb retail selling
  - Effective float (1 - cornerstone - intl placing) — tighter = less抛压
  - Issue price position (上下限定价)
  - Industry narrative — market pays premium for AI/具身/半导体/前沿生物
  - Market cap bucket (甜点 50-500 亿 HKD)
  - A+H discount (港股定价相对 A 股的折让)
  - Mechanism A/B (2025-08 new rule)

Running without the dynamic fields (oversub/cornerstone/A+H) is fine —
the scorer degrades gracefully. They can be supplied via overrides.json
or enriched via future data connectors.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional

# User capital in HKD — drives allocation sizing.
# Override via CAPITAL_HKD env var. Default 200k (user said 20万 HKD).
CAPITAL_HKD = float(os.environ.get("CAPITAL_HKD", "200000"))

# Effective leverage at 富途/辉立 for HK IPO 融资 (margin).
# Most 2026 IPOs: 90–99% margin, 0 interest, 100–200 HKD fixed fee per lot.
# Default 20x (富途 95% margin 主流档); hot IPOs can unlock 50-100x on request.
MARGIN_LEVERAGE = float(os.environ.get("MARGIN_LEVERAGE", "20.0"))

# Threshold amounts for 甲乙组 (HKEX rule: split at 500 万 HKD subscription value)
YI_TOU_HKD = 5_000_000      # 乙头 ≈ 500万申购，跨入乙组
JIA_WEI_HKD = 4_000_000     # 甲尾 ≈ 400万申购 (甲组最高档附近)
JIA_MID_HKD = 500_000       # 甲中 ≈ 50万申购 (摸彩性质)

# ---- Sponsor reputation lists ------------------------------------------------

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
    "中信建投", "China Securities",
    "海通国际", "Haitong International",
    "平安", "Ping An of China Capital",
    "BOCI", "中银国际",
    "华泰", "Huatai",
]

MID_SPONSORS = [
    "国泰君安", "Guotai Junan",
    "广发", "GF",
    "兴业",
    "农银国际", "ABCI",
    "建银国际", "CCB International",
    "工银国际", "ICBC International",
    "民银资本",
    "光大", "Everbright",
    "德意志", "Deutsche",
    "Nomura", "野村",
    "GF Capital",
    "Orient Capital",
]

# Sponsors with a historical "杀猪盘" reputation — keep empty by default.
# User can append known-weak investment banks based on their own risk tolerance.
# (Hardcoding names without verified data is irresponsible.)
BAD_SPONSORS: list[str] = [
    # "xxx 国际", "yyy 资本",  # add names you've personally had bad experience with
]

# ---- Cornerstone quality list -----------------------------------------------

TOP_CORNERSTONES = [
    "淡马锡", "Temasek",
    "GIC",
    "阿布扎比", "Abu Dhabi", "ADIA", "Mubadala",
    "加拿大养老", "CPPIB", "CPP Investment",
    "高瓴", "Hillhouse", "HHLR",
    "红杉", "Sequoia",
    "景林",
    "Aspex",
    "Black Rock", "BlackRock", "贝莱德",
    "Fidelity", "富达",
    "挪威", "NBIM",
    "中投", "CIC",
    "国家队", "汇金", "社保基金",
    "Temasek", "Schroders", "施罗德",
    "橡树", "Oaktree",
]

# ---- Industry narrative lists ------------------------------------------------
# Tier 1 (+2) — current hot narratives where market pays large premium
# Keywords are matched against both the sshy industry label AND the business
# description, so rich phrases like "基座模型" / "大模型" / "图计算" trigger.
TIER1_INDUSTRIES = [
    "AI", "人工智能", "认知智能",
    "大模型", "基座模型", "预训练模型",
    "具身智能", "humanoid", "人形机器人",
    "半导体设备", "EDA", "光刻",
    "创新药", "前沿生物", "mRNA", "ADC", "PD-1", "生物科技",
    "算力", "推理芯片", "GPU", "ASIC", "DPU", "NPU",
    "硅光", "光模块", "光芯片",
    "固态电池", "储能",
    "图计算",
    "自动驾驶", "智能驾驶",
    "芯片", "半导体", "Semiconductor", "semiconductor",
    "Biotech", "biotech",
    "Microelectronics",
]

# Tier 2 (+1) — generally favored sectors
TIER2_INDUSTRIES = [
    "硬件", "硬科技", "先进",
    "软件", "SaaS", "软件服务", "云计算",
    "机器人",  # generic robotics ≠ 具身智能; weaker premium

    "生物", "医疗器械", "医疗保健", "医药", "制药",
    "Biosciences", "Bioscience",
    "Pharmaceutical", "Pharma",
    "新能源", "电动", "锂电", "Battery",
    "航天", "卫星", "航空",
]

# Cold (-2) — sectors with weak demand / structural破发
COLD_INDUSTRIES = [
    "地产", "房地产", "Real Estate",
    "传统零售", "零售", "餐饮", "Retail",
    "纸业", "水泥", "钢铁", "Steel", "Cement",
    "教育", "K12", "Education",
    "纺织", "服装", "Apparel", "Textile",
    "物业", "物业管理",
    # 2026 data-driven additions: categories that consistently underperformed
    "饮料", "食品", "生猪", "养殖", "猪肉",
    "Beverage", "Foods", "Food",
    "文创", "工艺", "Cultural",
    "工业自动化", "工业机器人", "Automation", "AUTOMATION",
    "家庭电器", "家用电器",
    "工用支援", "包装服务",
    "户外", "服饰", "Outdoor",
    "汽车零部件",
]


@dataclass
class Score:
    total: int
    recommendation: str
    reasons: list[str]
    allocation: dict | None = None   # {"tier": ..., "subscribe_hkd": ..., "margin_hkd": ..., "note": ...}

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "recommendation": self.recommendation,
            "reasons": self.reasons,
            "allocation": self.allocation,
        }


def suggest_allocation(recommendation: str, capital: float = CAPITAL_HKD) -> dict:
    """Given recommendation bucket + user capital, propose a subscription size.

    Key economic truth: at 2026 low 甲组 allotment rates (<1% for hot IPOs),
    1 手现金 is effectively not participating. Real 打新 requires sufficient
    subscription size to either:
      - 乙头 (≥500万 HKD): guaranteed ≥1 lot + better 乙组 allotment
      - 甲尾 (~400万 HKD): typically wins 5-10 lots even in hot IPOs
    Modern brokers (富途/辉立) offer 90–99% 0-interest margin, so 20万 HKD
    cash is enough保证金 for these tiers.
    """
    def _margin_tag(margin: float) -> str:
        if margin <= capital * 0.5:
            return "✅ 本金充足，可并发多只"
        if margin <= capital * 1.0:
            return "🟡 保证金占大半本金，一次只能打 1 只；并发请用 100x"
        return "⚠️ 20x 杠杆保证金超本金，必须用 100x 杠杆"

    if recommendation == "STRONG_BUY_MARGIN_YIHEAD":
        subscribe = YI_TOU_HKD
        margin_20x = subscribe / 20
        margin_100x = subscribe / 100
        return {
            "tier": "YI_TOU",
            "subscribe_hkd": subscribe,
            "margin_hkd": margin_20x,
            "affordable": margin_20x <= capital * 0.9,
            "note": (
                f"🟢 融资打乙头 · 申购 ~{subscribe/1e4:.0f} 万 HKD · "
                f"保证金 20x={margin_20x/1e4:.0f} 万 / 100x={margin_100x/1e4:.1f} 万  "
                f"{_margin_tag(margin_20x)}"
            ),
            "expected_lots": "乙组保证 ≥1 手 + 红鞋机制下超购 >100x 时中 2-3 手",
        }
    if recommendation == "BUY_ONE_LOT":
        subscribe = JIA_WEI_HKD
        margin_20x = subscribe / 20
        margin_100x = subscribe / 100
        return {
            "tier": "JIA_WEI",
            "subscribe_hkd": subscribe,
            "margin_hkd": margin_20x,
            "affordable": margin_20x <= capital * 0.9,
            "note": (
                f"🟡 融资打甲尾 · 申购 ~{subscribe/1e4:.0f} 万 HKD · "
                f"保证金 20x={margin_20x/1e4:.0f} 万 / 100x={margin_100x/1e4:.1f} 万  "
                f"{_margin_tag(margin_20x)}"
            ),
            "expected_lots": "预期 3-10 手 (视超购)；超购 >100x 可升级乙头",
        }
    if recommendation == "WATCH":
        return {
            "tier": "WATCH",
            "subscribe_hkd": 0,
            "margin_hkd": 0,
            "affordable": True,
            "note": "⚪ 观望 · 核对超购后再定档",
            "expected_lots": (
                "若超购 >100x & 基石强 → 升级乙头 | "
                "若 15-50x → 放弃（踩踏区间）| <15x → 小额甲中档摸彩"
            ),
        }
    return {
        "tier": "SKIP",
        "subscribe_hkd": 0,
        "margin_hkd": 0,
        "affordable": True,
        "note": "🔴 放弃 · 不值得占用融资额度",
        "expected_lots": "—",
    }


def _any_match(haystack: str, needles: Iterable[str]) -> list[str]:
    h = haystack or ""
    return [n for n in needles if n and n in h]


def score_ipo(features: dict) -> Score:
    """Score an IPO.

    Feature keys (all optional):
      sponsor: str
      industry: str
      price_range: str
      issue_price_position: "low" | "high" | "mid" | None
      cornerstone_ratio: float 0..1 (锁仓比例)
      cornerstone_names: str (comma-joined)
      intl_placing_ratio: float 0..1 (国际配售占比)
      oversubscription_public: float (e.g. 180.0 = 180x)
      market_cap_hkd: float
      mechanism_b: bool
      ah_discount: float    — HK price vs A-share (+0.3 = HK 比 A 股便宜 30%)
    """
    total = 0
    reasons: list[str] = []

    # 1. Sponsor quality (including blacklist)
    sponsor = features.get("sponsor") or ""
    if sponsor:
        bads = _any_match(sponsor, BAD_SPONSORS)
        tops = _any_match(sponsor, TOP_SPONSORS)
        mids = _any_match(sponsor, MID_SPONSORS)
        if bads:
            total -= 3
            reasons.append(f"🔴 黑名单保荐: {', '.join(bads[:2])} (-3)")
        elif tops:
            total += 2
            reasons.append(f"✅ 顶级保荐: {', '.join(tops[:3])} (+2)")
        elif mids:
            total += 1
            reasons.append(f"🟡 中档保荐: {', '.join(mids[:3])} (+1)")
        else:
            reasons.append(f"⚪ 保荐: {sponsor[:40]} (0)")

    # 2. Cornerstone lockup ratio (the more locked, the less day-1 sell pressure)
    cs_ratio = features.get("cornerstone_ratio")
    if cs_ratio is not None:
        if cs_ratio >= 0.60:
            total += 2
            reasons.append(f"✅ 基石锁仓 {cs_ratio:.0%} (+2)")
        elif cs_ratio >= 0.40:
            total += 1
            reasons.append(f"🟡 基石锁仓 {cs_ratio:.0%} (+1)")
        elif cs_ratio < 0.20:
            total -= 1
            reasons.append(f"❌ 基石锁仓仅 {cs_ratio:.0%} (-1)")

    # 3. Cornerstone quality
    cs_names = features.get("cornerstone_names") or ""
    if cs_names:
        top_cs = _any_match(cs_names, TOP_CORNERSTONES)
        if top_cs:
            total += 2
            reasons.append(f"✅ 顶级基石: {', '.join(top_cs[:3])} (+2)")

    # 4. Public oversubscription — note the 15–50x "dead zone"
    # Logic: >100x → huge retail demand absorbs the 30% callback supply;
    # 15–50x → triggers max callback but insufficient hype → 踩踏区间;
    # <15x → no callback, float stays with institutions → controllable.
    os_ratio = features.get("oversubscription_public")
    if os_ratio is not None:
        if os_ratio >= 100:
            total += 4
            reasons.append(f"🔥 公开超购 {os_ratio:.0f}x >=100x (+4)")
        elif os_ratio >= 50:
            total += 2
            reasons.append(f"✅ 公开超购 {os_ratio:.0f}x (+2)")
        elif os_ratio >= 15:
            total -= 3
            reasons.append(f"⚠️ 公开超购 {os_ratio:.0f}x (15–50x 踩踏区间) (-3)")
        elif os_ratio >= 5:
            total += 1
            reasons.append(f"🟡 公开超购 {os_ratio:.1f}x (无回拨但有热度) (+1)")
        else:
            total -= 2
            reasons.append(f"❌ 公开超购 {os_ratio:.1f}x <5x，冷门且无庄家 (-2)")

    # 5. Effective float = 1 - cornerstone_ratio - intl_placing_ratio
    intl = features.get("intl_placing_ratio")
    if cs_ratio is not None and intl is not None:
        float_ratio = max(0.0, 1.0 - cs_ratio - intl)
        if float_ratio < 0.15:
            total += 1
            reasons.append(f"✅ 有效流通盘 {float_ratio:.0%} 极紧 (+1)")
        elif float_ratio > 0.50:
            total -= 1
            reasons.append(f"⚠️ 有效流通盘 {float_ratio:.0%}，抛压较大 (-1)")

    # 6. Issue price position
    pos = features.get("issue_price_position")
    if pos == "low":
        total += 1
        reasons.append("✅ 下限定价 (+1)")
    elif pos == "high":
        total -= 1
        reasons.append("⚠️ 上限定价 (-1)")

    # 7. Market cap bucket
    mc = features.get("market_cap_hkd")
    if mc is not None:
        b = mc / 1e8
        if 50 <= b <= 500:
            total += 1
            reasons.append(f"✅ 发行市值 {b:.0f} 亿，甜点区间 (+1)")
        elif b < 10:
            total -= 1
            reasons.append(f"❌ 发行市值 {b:.1f} 亿，偏小 (-1)")
        elif b > 1000:
            reasons.append(f"⚪ 发行市值 {b:.0f} 亿，巨无霸 (0)")

    # 8. Industry narrative — 2 tiers + cold list
    ind = features.get("industry") or ""
    if ind:
        t1 = _any_match(ind, TIER1_INDUSTRIES)
        t2 = _any_match(ind, TIER2_INDUSTRIES)
        cold = _any_match(ind, COLD_INDUSTRIES)
        if t1:
            total += 2
            reasons.append(f"🔥 顶级赛道: {ind} ({', '.join(t1[:2])}) (+2)")
        elif t2:
            total += 1
            reasons.append(f"✅ 热门赛道: {ind} (+1)")
        elif cold:
            total -= 2
            reasons.append(f"❌ 冷门赛道: {ind} (-2)")

    # 9. Mechanism B
    if features.get("mechanism_b"):
        total += 1
        reasons.append("✅ 采用机制B发行 (+1)")

    # 10. A+H discount (港股定价 vs A股当前价)
    ahd = features.get("ah_discount")
    if ahd is not None:
        if ahd >= 0.30:
            total += 2
            reasons.append(f"✅ A+H 折让 {ahd:.0%}，安全垫厚 (+2)")
        elif ahd >= 0.15:
            total += 1
            reasons.append(f"🟡 A+H 折让 {ahd:.0%} (+1)")
        elif ahd < 0:
            total -= 1
            reasons.append(f"⚠️ 港股对 A 股溢价 {-ahd:.0%} (-1)")

    rec = _recommendation(total)
    alloc = suggest_allocation(rec)
    return Score(total=total, recommendation=rec, reasons=reasons, allocation=alloc)


def _recommendation(score: int) -> str:
    # Calibrated against 2026 Q1 backtest population.
    # Stable-data max (sponsor + industry + market cap + keywords) ≈ 5–7;
    # reaching 8+ usually requires verified 基石/超购 on top.
    if score >= 6:
        return "STRONG_BUY_MARGIN_YIHEAD"   # 确认超购/基石后冲乙头
    if score >= 3:
        return "BUY_ONE_LOT"                 # 基本面 OK · 1 手现金
    if score >= 0:
        return "WATCH"                       # 一般 · 看超购再定
    return "SKIP"                            # 明显冷门 · 放弃


RECOMMENDATION_LABELS = {
    "STRONG_BUY_MARGIN_YIHEAD": "🟢 强推 · 融资打乙头",
    "BUY_ONE_LOT":              "🟡 基本面 OK · 融资打甲尾",
    "WATCH":                    "⚪ 观望 · 看超购再定档",
    "SKIP":                     "🔴 放弃",
}


def label(rec: str) -> str:
    return RECOMMENDATION_LABELS.get(rec, rec)


if __name__ == "__main__":
    demos = [
        ("Xizhi (hot AI, strong backing)", {
            "sponsor": "中国国际金融、海通国际",
            "industry": "硅光 / AI 算力",
            "cornerstone_ratio": 0.65,
            "intl_placing_ratio": 0.90,
            "cornerstone_names": "GIC, Aspex, 高瓴",
            "oversubscription_public": 180,
            "issue_price_position": "high",
            "market_cap_hkd": 180e8,
            "mechanism_b": True,
        }),
        ("Dead-zone offering (踩踏区间)", {
            "sponsor": "中信证券",
            "industry": "资讯科技",
            "oversubscription_public": 30,
            "cornerstone_ratio": 0.30,
            "market_cap_hkd": 60e8,
        }),
        ("Only basic sponsor info (NLR backtest)", {
            "sponsor": "China International Capital Corporation",
        }),
        ("A+H with deep discount", {
            "sponsor": "中金",
            "industry": "半导体",
            "ah_discount": 0.35,
            "oversubscription_public": 80,
            "cornerstone_ratio": 0.45,
            "intl_placing_ratio": 0.40,
        }),
    ]
    for name, feat in demos:
        s = score_ipo(feat)
        print(f"\n# {name}")
        print(f"score: {s.total}  →  {label(s.recommendation)}")
        for r in s.reasons:
            print("  ", r)
