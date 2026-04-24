# hk-ipo-monitor

港股打新监控 · 规则评分 · Telegram 推送 · 2026 回测。

每天自动抓 [AAStocks 即将上市新股](http://www.aastocks.com/sc/stocks/market/ipo/upcomingipo/company-summary) → 按攻略规则打分 → Telegram 推送"放弃 / 1 手现金 / 融资打乙头"建议。

## 功能

- **Monitor** — GitHub Actions 每天 09:00 / 17:00 HKT 自动跑，新股首次出现即推 TG
- **Scorer** — 8 维规则打分：保荐人 / 基石占比 / 基石质量 / 公开超购 / 定价位置 / 市值 / 行业 / 机制 A/B
- **Backtest** — 拉 HKEX 官方 `NLR2026_Eng.xlsx` + Yahoo Finance 首日开盘价，对比 4 种策略

## 安装 & 运行

```bash
git clone https://github.com/<你>/hk-ipo-monitor.git
cd hk-ipo-monitor
pip install -r requirements.txt
cp .env.example .env      # 填 TG_BOT_TOKEN / TG_CHAT_ID

python -m src.monitor --dry-run   # 本地看一下打分，不推送
python -m src.monitor             # 正式推 TG
python -m src.backtest            # 重跑 2026 回测 → data/backtest_2026.md
```

## 一次性配置 Telegram

1. Telegram 找 **@BotFather** → `/newbot` → 记下 `TG_BOT_TOKEN`（形如 `1234:ABCxyz...`）
2. 和自己的 bot 发一句 `hi`，然后浏览器打开 `https://api.telegram.org/bot<TOKEN>/getUpdates` → 从 JSON 里复制 `chat.id` → 作为 `TG_CHAT_ID`
3. GitHub repo → Settings → Secrets and variables → Actions → **New repository secret** → 加 `TG_BOT_TOKEN` 和 `TG_CHAT_ID`

## GitHub Actions

- `.github/workflows/monitor.yml` — 定时 + 手动触发，已推过的新股 `data/seen.json` 会 commit 回仓避免重复推
- `.github/workflows/backtest.yml` — 每周一自动刷新回测，也支持 Actions 页面手动点按钮

## 评分规则（scorer.py）

| 维度 | 正分 | 负分 |
|---|---|---|
| 保荐人 | 顶级 +2（中金/摩根士丹利/高盛/瑞银/中信/海通国际/招银国际 等） | — |
| 基石占比 | >60% +2, 40-60% +1 | <20% -1 |
| 基石质量 | 有 淡马锡/GIC/阿布扎比/高瓴/Aspex +2 | — |
| 公开超购 | >100x +3, 20-100x +2, 5-20x +1 | <2x -2 |
| 定价位置 | 下限 +1 | 上限 -1 |
| 发行市值 | 50–500 亿 +1 | <10 亿 -1 |
| 行业 | 硬科技/半导体/AI/生物医药 +1 | 传统地产/纸业 -1 |
| 机制 B | +1 | — |

| 总分 | 建议 |
|---|---|
| ≥ 7 | 🟢 强推 · 融资打乙头 |
| 4 – 6 | 🟡 1 手现金 |
| 1 – 3 | ⚪ 观望 / 看暗盘 |
| ≤ 0 | 🔴 放弃 |

## 数据源

- **即将上市**：AAStocks `/stocks/market/ipo/upcomingipo/company-summary` — 代码、名称、价格区间、每手、入场费、招股期、上市日期、保荐人、市值区间
- **历史 IPO**：HKEX 官方 [`NLR2026_Eng.xlsx`](https://www2.hkexnews.hk/-/media/HKEXnews/Homepage/New-Listings/New-Listing-Information/New-Listing-Report/Main/NLR2026_Eng.xlsx) — 代码、名称、上市日期、招股价、保荐人、募资额
- **首日 OHLC**：yfinance (Yahoo) → akshare 东财后端 fallback

## 2026 回测结果

最新结果见 [data/backtest_2026.md](data/backtest_2026.md)。样本：2026-01-01 至今的 43 只主板 IPO。

> ⚠️ 回测时仅有 HKEX NLR 公开字段（发行价 + 保荐人 + 上市日），基石 / 超购倍数当时不可知。所以 B/C 策略在回测里退化成"以保荐人质量为主"，而 Monitor 实盘会多维度打分。

## 目录结构

```
hk-ipo-monitor/
├── .github/workflows/
│   ├── monitor.yml        # 定时监控
│   └── backtest.yml       # 回测刷新
├── src/
│   ├── fetcher.py         # AAStocks 抓取
│   ├── scorer.py          # 规则打分
│   ├── telegram.py        # TG 推送
│   ├── storage.py         # seen.json 去重
│   ├── monitor.py         # 编排入口
│   └── backtest.py        # 2026 回测
├── data/
│   ├── seen.json          # 已推送过的代码（workflow 自动 commit）
│   └── backtest_2026.md   # 回测报告
├── requirements.txt
└── .env.example
```

## 免责

仅为技术 demo，**不构成投资建议**。港股打新有破发风险，融资利息、手续费、中签率均需自行核算。
