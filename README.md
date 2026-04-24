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

思路是"开盘即卖"：赚流动性和情绪溢价，不持长线。

| 维度 | 正分 | 负分 |
|---|---|---|
| 保荐人 | 顶级 +2（中金/摩根士丹利/高盛/瑞银/中信/海通国际/招银国际/华泰 等）<br>中档 +1 | 黑名单 -3（默认空，可自行维护） |
| 基石锁仓比例 | >60% +2, 40-60% +1 | <20% -1 |
| 基石质量 | 顶级机构（淡马锡/GIC/阿布扎比/高瓴/Aspex/国家队）+2 | — |
| 公开超购倍数 | >100x **+4**, 50-100x +2, 5-15x +1 | **15-50x -3**（触发回拨但承接力不足的踩踏区间）<br><5x -2 |
| 有效流通盘 | (1-基石-国配) <15% +1 | >50% -1 |
| 定价位置 | 下限 +1 | 上限 -1 |
| 发行市值 | 50-500 亿 +1 | <10 亿 -1 |
| 赛道（分 3 档） | **Tier 1 +2**: AI/大模型/具身智能/机器人/半导体设备/前沿生物/算力<br>Tier 2 +1: 半导体/硬科技/医疗器械/新能源 | 冷门 -2: 地产/传统消费/纸业/K12/物业 |
| 机制 B | +1 | — |
| A+H 折让 | >30% +2, 15-30% +1 | 港股溢价 -1 |

| 总分 | 建议 |
|---|---|
| ≥ 9 | 🟢 强推 · 融资打乙头 |
| 5 – 8 | 🟡 1 手现金 |
| 1 – 4 | ⚪ 观望 / 看暗盘 |
| ≤ 0 | 🔴 放弃 |

### 工作流

Scorer 只吃公开页稳定抓得到的字段（保荐人 / 行业 / 市值 / 招股价区间）给一个**基础分 + 初步建议**，TG 消息里给你一个决定。然后在末尾附**自行核对清单**，把公开页抓不稳的动态信号以阈值提示形式列给你：

- **公开超购倍数**（富途 / 捷利）—— >100x 可冲乙头；15-50x 踩踏区间建议避开
- **基石锁仓比例**（招股书 / 捷利港信）—— >60% 抛压小；顶级基石（淡马锡 / GIC / 阿布扎比 / 高瓴）再加一档
- **A+H 折让**（只在 H 股出现）—— 看当日 A 股收盘价，折让 >30% 安全垫厚

> 这三个字段试过 AAStocks / 富途 / 捷利 / 东财 / 新浪 / 新股预付，全都是 JS 渲染或登录墙，无法稳定自动抓；因此只给提示不进基础分。如果你自己查出来的结果明显翻转建议（比如"观望"的股发现超购 200 倍），请自行决定。

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
