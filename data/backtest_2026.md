# 港股打新 2026 回测

生成时间: 2026-04-23 22:26

数据源: HKEX NLR2026_Eng.xlsx + yfinance

样本: 43 只 2026 主板新股 (41 只有首日开盘价)

## 策略汇总

| 策略 | 参与数 | 胜率 | 平均首日 % | 累计 % |
|---|---:|---:|---:|---:|
| A · 全打 1 手 | 41 | 83% | +41.33% | +1694.68% |
| B · 筛选 (非 SKIP) 1 手 | 40 | 82% | +41.74% | +1669.68% |
| C · 强推 (score≥7) 1 手 | 0 | 0% | +0.00% | +0.00% |
| D · 仅顶级保荐 (score≥2) 1 手 | 37 | 81% | +40.21% | +1487.92% |

> ⚠️ 回测输入仅含 HKEX NLR 公开字段（代码、发行价、上市日期、保荐人）。
> 基石强度/超购倍数在回测时点无法还原，因此 B/C 策略以保荐人质量为主，
> 实盘 Monitor 会多维度打分（见 scorer.py）。

最佳: 02706 Beijing Haizhi Techn +204.14%
最差: 00664 Hangzhou Tongshifu C -40.97%

## 明细

| 代码 | 名称 | 上市日 | 招股价 | 首日开盘 | 涨跌% | 分数 | 建议 | 保荐 |
|---|---|---|---:|---:|---:|---:|---|---|
| 06082 | Shanghai Biren Technology Co., | 2026-01-02 | 19.600 | 35.700 | +82.14% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 02513 | Knowledge Atlas Technology Joi | 2026-01-08 | 116.200 | 120.000 | +3.27% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 09903 | Shanghai Iluvatar CoreX Semico | 2026-01-08 | 144.600 | 190.200 | +31.54% | 2 | ⚪ 观望 / 看暗盘 | Huatai Financial Holdings (Hong Kong) Li |
| 02675 | Shenzhen Edge Medical Co., Ltd | 2026-01-08 | 43.240 | 59.000 | +36.45% | 2 | ⚪ 观望 / 看暗盘 | Morgan Stanley Asia Limited / GF Capital |
| 00100 | MiniMax Group Inc. - W - P | 2026-01-09 | 165.000 | — | — | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 06938 | Suzhou Ribo Life Science Co.,  | 2026-01-09 | 57.970 | 75.000 | +29.38% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 03636 | Yunnan Jinxun Resources Co., L | 2026-01-09 | 30.000 | 38.000 | +26.67% | 2 | ⚪ 观望 / 看暗盘 | Huatai Financial Holdings (Hong Kong) Li |
| 00501 | OmniVision Integrated Circuits | 2026-01-12 | 104.800 | — | — | 2 | ⚪ 观望 / 看暗盘 | UBS Securities Hong Kong Limited /  Chin |
| 03986 | GigaDevice Semiconductor Inc.  | 2026-01-13 | 162.000 | 235.000 | +45.06% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 01641 | Hongxing Coldchain (Hunan) Co. | 2026-01-13 | 12.260 | 19.580 | +59.71% | 1 | ⚪ 观望 / 看暗盘 | CCB International Capital Limited / ABCI |
| 09611 | Shanghai Longcheer Technology  | 2026-01-22 | 31.000 | 35.000 | +12.90% | 2 | ⚪ 观望 / 看暗盘 | Citigroup Global Markets Asia Limited /  |
| 01768 | BUSY MING GROUP CO., LTD.- H s | 2026-01-28 | 236.600 | 445.000 | +88.08% | 2 | ⚪ 观望 / 看暗盘 | Goldman Sachs (Asia) L.L.C /  Huatai Fin |
| 09980 | Eastroc Beverage (Group) Co.,  | 2026-02-03 | 248.000 | 248.000 | +0.00% | 2 | ⚪ 观望 / 看暗盘 | Huatai Financial Holdings (Hong Kong) Li |
| 02768 | Qingdao Gon Technology Co., Lt | 2026-02-04 | 36.000 | 45.000 | +25.00% | 0 | 🔴 放弃 | China Merchants Securities (HK) Co., Lim |
| 02677 | Distinct Healthcare Holdings L | 2026-02-06 | 59.900 | 81.000 | +35.23% | 2 | ⚪ 观望 / 看暗盘 | Haitong International Capital Limited /  |
| 02714 | Muyuan Foods Co., Ltd. - H sha | 2026-02-06 | 39.000 | 39.000 | +0.00% | 2 | ⚪ 观望 / 看暗盘 | Morgan Stanley Asia Limited /  CITIC Sec |
| 03200 | Shenzhen Han’s CNC Technology  | 2026-02-06 | 95.800 | 106.000 | +10.65% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 06809 | Montage Technology Co., Ltd. - | 2026-02-09 | 106.890 | 168.000 | +57.17% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 00600 | Axera Semiconductor Co., Ltd.  | 2026-02-10 | 28.200 | 28.200 | +0.00% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 02720 | Ridge Outdoor International Li | 2026-02-10 | 12.250 | 24.020 | +96.08% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 00470 | WUXI LEAD INTELLIGENT EQUIPMEN | 2026-02-11 | 45.800 | 46.260 | +1.00% | 2 | ⚪ 观望 / 看暗盘 | CITIC Securities (Hong Kong) Limited /   |
| 02706 | Beijing Haizhi Technology Grou | 2026-02-13 | 27.060 | 82.300 | +204.14% | 2 | ⚪ 观望 / 看暗盘 | CMB International Capital Limited / BOCI |
| 09981 | Shenzhen Woer Heat-Shrinkable  | 2026-02-13 | 20.090 | 20.100 | +0.05% | 2 | ⚪ 观望 / 看暗盘 | China Securities (International) Corpora |
| 02649 | ALSCO Pooling Service Co., Ltd | 2026-03-09 | 11.000 | 7.500 | -31.82% | 2 | ⚪ 观望 / 看暗盘 | China Securities (International) Corpora |
| 02715 | ESTUN AUTOMATION CO., LTD - H  | 2026-03-09 | 15.360 | 15.360 | -0.00% | 2 | ⚪ 观望 / 看暗盘 | Huatai Financial Holdings (Hong Kong) Li |
| 02692 | Shenzhen Zhaowei Machinery & E | 2026-03-09 | 71.280 | 78.000 | +9.43% | 1 | ⚪ 观望 / 看暗盘 | China Merchants Securities (HK) Co., Lim |
| 03268 | MeiG Smart Technology Co., Ltd | 2026-03-10 | 28.860 | 29.040 | +0.62% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 01989 | Delton Technology (Guangzhou)  | 2026-03-20 | 71.880 | 90.850 | +26.39% | 2 | ⚪ 观望 / 看暗盘 | CITIC Securities (Hong Kong) Limited / H |
| 02701 | Nsing Technologies Inc. - H Sh | 2026-03-23 | 10.800 | 14.300 | +32.41% | 2 | ⚪ 观望 / 看暗盘 | CITIC Securities (Hong Kong) Limited |
| 03355 | FS.COM Ltd. - H Shares | 2026-03-23 | 41.600 | 56.000 | +34.62% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 02632 | Jiangsu New Vision Automotive  | 2026-03-24 | 44.200 | 43.900 | -0.68% | 2 | ⚪ 观望 / 看暗盘 | Haitong International Capital Limited. / |
| 02729 | Zhejiang Galaxis Technology Gr | 2026-03-24 | 16.660 | 32.000 | +92.08% | 2 | ⚪ 观望 / 看暗盘 | Guotai Junan Capital Limited / CITIC Sec |
| 01021 | Guangdong Huayan Robotics Co., | 2026-03-30 | 17.000 | 16.800 | -1.18% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 02526 | Hangzhou Diagens Biotechnology | 2026-03-30 | 99.000 | 219.000 | +121.21% | 2 | ⚪ 观望 / 看暗盘 | Huatai Financial Holdings (Hong Kong) Li |
| 02726 | Epiworld International Co., Lt | 2026-03-30 | 76.260 | 110.000 | +44.24% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |
| 06636 | Shandong Extreme Vision Techno | 2026-03-30 | 40.000 | 59.950 | +49.88% | 2 | ⚪ 观望 / 看暗盘 | CITIC Securities (Hong Kong) Limited |
| 00664 | Hangzhou Tongshifu Cultural an | 2026-03-31 | 60.000 | 35.420 | -40.97% | 2 | ⚪ 观望 / 看暗盘 | CMB International Capital Limited |
| 03625 | Shanghai FourSemi Semiconducto | 2026-03-31 | 40.000 | 85.050 | +112.63% | 1 | ⚪ 观望 / 看暗盘 | Guotai Junan Capital Limited / Orient Ca |
| 06656 | Sigenergy Technology Co., Ltd. | 2026-04-16 | 324.200 | 581.000 | +79.21% | 2 | ⚪ 观望 / 看暗盘 | CITIC Securities (Hong Kong) Limited / B |
| 03277 | Gpixel Changchun Microelectron | 2026-04-17 | 39.880 | 72.000 | +80.54% | 2 | ⚪ 观望 / 看暗盘 | CITIC Securities (Hong Kong) Limited/ Gu |
| 00068 | Manycore Tech Inc. | 2026-04-17 | 7.620 | 20.700 | +171.65% | 2 | ⚪ 观望 / 看暗盘 | J.P. Morgan Securities (Far East) Limite |
| 02476 | Victory Giant Technology (HuiZ | 2026-04-21 | 209.880 | 330.000 | +57.23% | 2 | ⚪ 观望 / 看暗盘 | J.P. Morgan Securities (Far East) Limite |
| 03296 | Huaqin Co., Ltd. - H Shares | 2026-04-23 | 77.700 | 87.550 | +12.68% | 2 | ⚪ 观望 / 看暗盘 | China International Capital Corporation  |