# hk-ipo-monitor

港股打新监控 · 规则评分 · 档位建议 · Telegram 推送 · 2026 回测。

每天自动抓 [AAStocks 即将上市新股](http://www.aastocks.com/sc/stocks/market/ipo/upcomingipo/company-summary) → 按攻略规则打分 → Telegram 推送具体档位建议（融资打乙头 / 甲尾 / 放弃）。

## 为什么不是"1 手现金"？

2026 热门 IPO 一手中签率常 <1%，甚至 <0.1%。用 20 万本金全打 1 手 = 实际中签几乎为零 = 等于没打。用 2026 Q1 数据回测：

| 策略 | 2026 累计盈亏 |
|---|---:|
| 🔴 全打 1 手现金 | **+1,356 HKD** |
| 🟡 全打甲尾融资 | **+338,937 HKD** |
| 🟢 scorer 分档（强推乙头 / BUY 甲尾）| **+260,707 HKD** |

所以 bot 的建议按档位发，不再是"1 手"。券商（富途/辉立）对热门 IPO 给 20-100x 融资、0 利息、~200 HKD/手固定手续费，20 万保证金能撑得起乙头。

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

## 🧸 傻瓜式六步走（5 分钟搞定）

不用服务器、不用 Cloudflare，全靠 GitHub Actions 白嫖。

### 1️⃣ 创建 Telegram Bot

- Telegram 搜 **@BotFather**（蓝色 ✓ 认证）
- 发 `/newbot` → 按提示起名、起 username（必须 `bot` 结尾，例如 `caleaf_hkipo_bot`）
- 复制它回复里那串 `TG_BOT_TOKEN`（形如 `1234567890:AAHxxxxxxxx`）备用

### 2️⃣ 和 bot 说一句话

- 点 BotFather 回复里的 bot 链接 → **Start** → 发一句 `hi`
- （必须发，不然下一步拿不到 chat_id）

### 3️⃣ 拿 Chat ID

浏览器打开（`<TOKEN>` 换成第 1 步的 token）：

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

从返回的 JSON 里找 `"chat":{"id":123456789,...` — 这个数字就是 `TG_CHAT_ID`。

> 看到 `{"ok":true,"result":[]}` 说明第 2 步没发消息，回去补一句 `hi`。

### 4️⃣ 加 GitHub Secrets

打开 `https://github.com/<你>/hk-ipo-monitor/settings/secrets/actions` → 点 **New repository secret**，加两条：

| Name | Secret |
|---|---|
| `TG_BOT_TOKEN` | 第 1 步复制的 token |
| `TG_CHAT_ID` | 第 3 步那串数字 |

### 5️⃣ 手动触发一次验证

- 打开 `https://github.com/<你>/hk-ipo-monitor/actions/workflows/monitor.yml`
- 右上角 **Run workflow** → 分支 `main` → 绿色 Run workflow
- 等 2-3 分钟（黄点 → 绿勾）
- 手机 Telegram 应该会收到当前 4 只即将上市的新股推送

### 6️⃣ 完事

之后每天 HKT **09:00 / 17:00** 自动跑。有新股就推，没有就静默。

### 🚨 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| Run workflow 变红 ❌ | token / chat_id 错了 | 点那次 run → 看 `Run monitor` step 日志 |
| 绿勾 ✅ 但 TG 没收到 | chat_id 填错 / bot 被静音 | 回第 3 步重拿；检查 TG 里 bot 通知设置 |
| 一个月后自动停 | GitHub 60 天没 activity 会禁用 cron | 每月手动 Run workflow 一次，或正常有 commit 也行 |
| 推送延迟几分钟 | GitHub cron 峰期会延迟 | 正常现象；不要指望抢招股最后 5 分钟的热度 |

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

| 总分 | 建议档位 | 申购额 | 保证金 (20x/100x) | 中签预期 |
|---|---|---:|---:|---|
| ≥ 6 | 🟢 **融资打乙头** | 500 万 | 25 万 / 5 万 | 保证 ≥1 手 + 热门中 2-3 手 |
| 3 – 5 | 🟡 **融资打甲尾** | 400 万 | 20 万 / 4 万 | 预期 3-10 手 |
| 0 – 2 | ⚪ 观望 | — | — | 看超购 >100x 升乙头 / 15-50x 放弃 |
| ≤ -1 | 🔴 放弃 | — | — | — |

阈值按 2026 Q1 实际 43 只 IPO 回测校准：
- **破发段平均分 1.80** vs **大涨段平均分 3.00** — scorer 能用公开字段区分明显的地雷
- 资金规模通过 `CAPITAL_HKD` 环境变量配置（默认 20 万）
- 杠杆率通过 `MARGIN_LEVERAGE` 配置（默认 20x，热门 IPO 富途可开 100x）

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
