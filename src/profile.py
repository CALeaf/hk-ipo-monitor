"""Fetch HK stock company profile from eastmoney HKF10.

Provides:
  - Industry classification (sshy)
  - Business description (gsjs) — rich narrative keywords

Used by backtest to enrich each historical IPO with industry signal beyond
what HKEX NLR exposes. Live Monitor already gets industry from AAStocks.
"""

from __future__ import annotations

import requests
from dataclasses import dataclass


EM_PROFILE_URL = (
    "https://emweb.securities.eastmoney.com/PC_HKF10/CompanyProfile/PageAjax?code={code}"
)


@dataclass
class Profile:
    code: str
    industry: str        # sshy — 所属行业 (e.g. "软件服务", "其他医疗保健")
    description: str     # gsjs — 公司业务简介 (rich narrative keywords)

    def combined(self) -> str:
        """Industry + description, used for keyword matching in scorer."""
        return f"{self.industry} {self.description}".strip()


def fetch(code: str, *, timeout: int = 10) -> Profile | None:
    """Fetch profile for a 5-digit HK code. Returns None on failure."""
    try:
        r = requests.get(
            EM_PROFILE_URL.format(code=code),
            headers={"User-Agent": "Mozilla/5.0 (hk-ipo-monitor)"},
            timeout=timeout,
        )
        d = r.json()
    except Exception:
        return None

    gszl = d.get("gszl") or {}
    ind = str(gszl.get("sshy") or "").strip()
    # eastmoney sometimes returns literal "—" or "--" as placeholders
    if ind in ("—", "--", ""):
        ind = ""
    desc = str(gszl.get("gsjs") or "").strip()
    if not ind and not desc:
        return None
    return Profile(code=code, industry=ind, description=desc)


if __name__ == "__main__":
    import sys
    for c in sys.argv[1:] or ["02526", "00664"]:
        p = fetch(c)
        if p:
            print(f"{c}: industry={p.industry!r}")
            print(f"     desc={p.description[:100]}")
        else:
            print(f"{c}: FAILED")
