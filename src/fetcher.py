"""Scrape AAStocks upcoming HK IPO list + per-stock detail."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE = "http://www.aastocks.com"
LIST_URL = f"{BASE}/sc/stocks/market/ipo/upcomingipo/company-summary"
DETAIL_URL = f"{BASE}/sc/stocks/market/ipo/upcomingipo/company-summary?symbol={{code}}"
HEADERS = {"User-Agent": "Mozilla/5.0 (hk-ipo-monitor)"}


@dataclass
class IPO:
    code: str
    name: str
    industry: str = ""
    price_range: str = ""
    lot_size: Optional[int] = None
    entry_fee: Optional[float] = None
    apply_deadline: str = ""
    grey_market_date: str = ""
    list_date: str = ""
    sponsor: str = ""
    market_cap_low: Optional[float] = None
    market_cap_high: Optional[float] = None
    hk_placing_shares: Optional[int] = None
    total_shares_m: Optional[float] = None
    detail_url: str = ""
    raw: dict = field(default_factory=dict)

    def min_price(self) -> Optional[float]:
        if not self.price_range:
            return None
        nums = re.findall(r"[\d.]+", self.price_range)
        return float(nums[0]) if nums else None

    def max_price(self) -> Optional[float]:
        if not self.price_range:
            return None
        nums = re.findall(r"[\d.]+", self.price_range)
        return float(nums[-1]) if nums else None

    def to_dict(self) -> dict:
        return asdict(self)


def _fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def _find_upcoming_table(soup: BeautifulSoup):
    """Find the main upcoming-IPO table by matching the header row."""
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        if not rows:
            continue
        headers = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        blob = " ".join(headers)
        if "招股价" in blob and "上市日期" in blob and "每手" in blob:
            return t
    return None


def _parse_code_name(cell_text: str) -> tuple[str, str]:
    m = re.search(r"(\d{5})\.HK", cell_text)
    code = m.group(1) if m else ""
    name = re.sub(r"\d{5}\.HK", "", cell_text).strip()
    return code, name


def list_upcoming() -> list[IPO]:
    html = _fetch(LIST_URL)
    soup = BeautifulSoup(html, "lxml")
    table = _find_upcoming_table(soup)
    if table is None:
        return []

    rows = table.find_all("tr")
    header = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]

    def col(name_substr: str) -> int:
        for i, h in enumerate(header):
            if name_substr in h:
                return i
        return -1

    i_name = col("公司名称")
    i_ind = col("行业")
    i_price = col("招股价")
    i_lot = col("每手")
    i_fee = col("入场费")
    i_deadline = col("招股截止")
    i_grey = col("暗盘")
    i_listdate = col("上市日期")

    out: list[IPO] = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < max(i_name, i_listdate) + 1:
            continue
        name_cell = cells[i_name] if i_name >= 0 else ""
        code, name = _parse_code_name(name_cell)
        if not code:
            continue
        ipo = IPO(
            code=code,
            name=name,
            industry=cells[i_ind] if i_ind >= 0 else "",
            price_range=cells[i_price] if i_price >= 0 else "",
            lot_size=_to_int(cells[i_lot]) if i_lot >= 0 else None,
            entry_fee=_to_float(cells[i_fee]) if i_fee >= 0 else None,
            apply_deadline=cells[i_deadline] if i_deadline >= 0 else "",
            grey_market_date=cells[i_grey] if i_grey >= 0 else "",
            list_date=cells[i_listdate] if i_listdate >= 0 else "",
            detail_url=DETAIL_URL.format(code=code),
        )
        out.append(ipo)
    return out


def enrich_detail(ipo: IPO) -> IPO:
    """Fetch detail page for a stock to fill sponsor / market cap / shares."""
    try:
        html = _fetch(ipo.detail_url)
    except Exception:
        return ipo
    soup = BeautifulSoup(html, "lxml")

    label_map: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) >= 2:
            k = cells[0].get_text(" ", strip=True)
            v = cells[1].get_text(" ", strip=True)
            if k and v and k not in label_map:
                label_map[k] = v

    ipo.sponsor = label_map.get("保荐人", ipo.sponsor) or ""
    mc = label_map.get("上市市值") or label_map.get("上市市值 ") or ""
    if mc:
        nums = re.findall(r"[\d,]+\.?\d*", mc)
        nums = [float(n.replace(",", "")) for n in nums if n]
        if len(nums) >= 2:
            ipo.market_cap_low, ipo.market_cap_high = nums[0], nums[-1]
        elif nums:
            ipo.market_cap_low = ipo.market_cap_high = nums[0]

    hk_shares = label_map.get("香港配售股份数目") or label_map.get("公开发售股份数目") or ""
    if hk_shares:
        m = re.search(r"([\d,]+)", hk_shares)
        if m:
            ipo.hk_placing_shares = int(m.group(1).replace(",", ""))

    ipo.raw = label_map
    return ipo


def _to_int(s: str) -> Optional[int]:
    m = re.search(r"[\d,]+", s or "")
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _to_float(s: str) -> Optional[float]:
    m = re.search(r"[\d,]+\.?\d*", s or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


if __name__ == "__main__":
    ipos = list_upcoming()
    print(f"found {len(ipos)} upcoming IPOs")
    for ipo in ipos:
        enrich_detail(ipo)
        print(
            f"  {ipo.code} {ipo.name} | {ipo.industry} | {ipo.price_range} @ {ipo.lot_size}股"
            f" | list={ipo.list_date} | sponsor={ipo.sponsor[:60]}"
        )
