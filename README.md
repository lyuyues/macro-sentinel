AI Stock Valuation Toolkit

Automatically calculate stock fair value using SEC EDGAR financial data, then screen the entire US market for undervalued stocks.

## Setup

```bash
pip install pandas numpy requests yfinance openpyxl
```

Python 3.9+ required. Uses `/Users/y32lyu/miniforge3/bin/python3` on this machine.

## Files

| File | Purpose |
|------|---------|
| `dcf_builder.py` | Core DCF engine — fetches SEC data, computes margins, runs 10-year 3-stage DCF |
| `dcf_utils.py` | Helpers — Stooq prices, SIC-to-sector mapping, year-end prices (yfinance), WACC |
| `valuation_builder.py` | Full valuation template — income statement, balance sheet, cash flow, ratios, DCF |
| `dcf_screener.py` | Batch screener — runs DCF on many tickers, filters undervalued stocks |
| `get_all_ticker.py` | Downloads all US ticker list from SEC |

## Usage

### 1. Single Stock DCF (quick)

```bash
python dcf_builder.py --ticker GOOGL --required 0.07 --perp 0.025 --avg-years 5
```

Or edit `dcf_builder.py` bottom and run directly:
```python
run_dcf_once(ticker="TSLA", sector="TECH")
```

**Output files:**
- `2026_dcf_TSLA_10K.csv` — historical financials (Revenue, Net Income, FCF, margins)
- `2026_dcf_TSLA_proj.csv` — 10-year DCF projection (transposed: years as columns, metrics as rows)
- `2026_dcf_TSLA_meta.json` — summary (fair value, growth rates, assumptions)

**Optional flags:**
- `--save-raw-json` — save full SEC companyfacts JSON
- `--save-raw-csv` — save flattened SEC data as CSV
- `--sector TECH` — manually override sector (TECH / CONSUMER / BANK / INSURANCE / ENERGY / PHARMA)

### 2. Full Valuation Template (comprehensive)

```bash
python valuation_builder.py --ticker AMD
```

**Output:** `valuation_AMD.csv` with sections:
- Company Info (ticker, sector, WACC, fair value)
- Income Statement (Revenue, Gross Profit, Operating Income, EBITDA, D&A, Interest, Tax, Net Income, EPS, DPS, margins)
- Balance Sheet (Cash, Short/Long-term Debt, Total Assets, Equity, Shares Outstanding)
- Cash Flow (CFO, CapEx, FCF, FCF Margin)
- Valuation Ratios (Market Cap, EV, P/E, P/S, P/B, EV/Revenue, EV/EBITDA, ROE, ROA, ROIC)
- DCF Projection (10-year projected Revenue, FCF, discount factors, PV)

**For Excel output** (separate sheets per section):
```bash
python valuation_builder.py --ticker AMD --excel
```

**All flags:**
```
--ticker       Stock ticker (required)
--required     Discount rate, default 0.07
--perp         Perpetual growth rate, default 0.025
--avg-years    Years for averaging margins, default 5
--projection-years  DCF projection years, default 10
--output       Custom output filename
--excel        Also save as .xlsx
```

### 3. Batch Screening (find undervalued stocks)

Edit `dcf_screener.py` bottom to set parameters, then run:
```bash
python dcf_screener.py
```

Requires a ticker list CSV (from `get_all_ticker.py`). Outputs:
- `dcf_screen_all_<timestamp>.csv` — all results
- `dcf_screen_undervalued_<timestamp>.csv` — stocks with discount >= threshold

### 4. Get All US Tickers

```bash
python get_all_ticker.py
```

Downloads the full SEC ticker list to `all_us_tickers_sec.csv`.

## Examples

```bash
# Quick DCF for Apple
python dcf_builder.py --ticker AAPL

# Full valuation for NVIDIA with Excel
python valuation_builder.py --ticker NVDA --excel

# DCF with custom parameters
python dcf_builder.py --ticker MSFT --required 0.08 --perp 0.02 --sector TECH

# Full valuation with 15-year projection
python valuation_builder.py --ticker GOOGL --projection-years 15
```





Argument for dcf_builder
# --ticker：股票代码（如 AAPL、GOOGL、BWXT）
# --required：折现率（默认 0.07）
# --perp：永续增长率（默认 0.025）
# --years：显性预测年数（默认 4）
# --avg-years：计算平均净利率/比值的历史年数（默认 5）


# 平均净利润率 avg_net_margin (%) = avg(net_income / revenue) 取最近 avg_years 年
# FCF/Net Income 比率 avg_fcf_to_ni (%) = avg(fcf / net_income) 取最近 avg_years 年 
<!-- note：如果某些年份 net_income 非常小，就会让 ratio 爆炸（比如 3000%） -->
# Adopted Growth Rate (%) = growth = revenue_CAGR (last n years)
# growth = profit_CAGR

# 知识点
投资目标是想要更多的自由现金流（FCF），which可真实可用来：
	•	分红
	•	回购
	•	投资
	•	还债
	•	收购
    的现金

⚠ 高成长公司（TSLA、AMZN）通常 FCF 会低，因为 CapEx 资本开支投入（是现金支出不是费用，减少现金但不变利润）巨大。
净利润并不会全部流入自由现金流，因为：
	•	应收账款增加（客户未付款）
	•	存货增加（现金被占用）
	•	各类营运资本变动
	•	折旧是非现金费用
	•	资本开支（CapEx）需要大量现金
	•	税务结构导致部分利润不等于现金流



# 计算逻辑
## 自由现金流与利润率
### 自由现金流（FCF）= 经营现金流 - 资本支出
    FCF = CFO - CapEx

    CFO（Cash Flow from Operations）：经营活动产生的现金流
	CapEx（Capital Expenditures）：资本支出，用于购买固定资产（如设备、厂房）

### 年度净利率（Net Profit Margin）= 年度净收入 / 利润  
    NetMargin_y = Net Income_y / Revenue_y
表示公司每赚 1 美元营收，最终能留下多少净利润，越大越好

### 年度 FCF / 净利润比（FCF to Profit Margin）= 年度自由现金流 / 年度净收入
    FCF_to_NI_y = FCF_y / Net Income_y
    Net Income_y = Revenues - Operating Expenses – Interest – Taxes (是个statement现成的值)
该指标用于衡量公司的净利润有多少最终转化成自由现金流（Free Cash Flow）。
它描述了盈利的“含金量”。

## 平均指标（最近 N 年，默认 5 年）
### Avg Net Profit Margin (%)：最近 avg_years 年 NetMargin 的均值
### Avg FCF/Net Income (%)：最近 avg_years 年 FCF_to_NI 的均值

## 增长率（Adopted Growth Rate）预测未来的增长率
    函数 adopt_growth_rate(ticker, revenue) 负责决定未来收入增长率：
        1.	优先尝试：yfinance 分析师预测
        •	若 t.earnings_forecasts["revenueEstimate"]["growth"] 可用，则直接用
        2.	否则：回退到 Revenue CAGR
        •	取最近最多 5 年的 Revenue，计算 CAGR （CAGR = Compound Annual Growth Rate，中文通常翻译为 复合年增长率。适合做味长期增长率的估算，适合反应长期复利增长，但如果波动很大，比如一涨一跌，CAGR可能=0% 容易失真）
        3.	再否则：兜底值
        •	使用一个保守常数 growth = 0.05（5%）
    最终写入 meta.csv

## 预测与折现逻辑
    假设最后一个有营收数据的年份为 last_year，基于此向后预测 projection_years（默认 4 年）。
### 收入预测
    Revenue_t = Revenue_{t-1} * (1 + g)
    其中 g = Adopted Growth Rate
### FCF 利润率
    优先使用： FCF Margin = Avg Net Margin * Avg FCF/Net Income
    若缺失则回退为最近几年 FCF / Revenue 的平均值，否则兜底为 15%。
### 预测 FCF
    FCF_t = Revenue_t * FCF Margin
### 折现因子
    DF_t = (1 + r)^t 
    r = Required Return
### 未来 FCF 现值
    PV-FCF_t = FCF_t / DF_t
### 终值（Terminal Value，永续增长模型）
    FCF_terminal = FCF_last * (1 + g_infinity)
    TV =  FCF_terminal / (r - g_infinity)
    PV_Terminal = TV / (1 + r)^projection_years

### 企业价值与每股价值
    Enterprise Value = Sum(PV-FCF_t) + PV_Terminal 
    Fair Value / Share = Enterprise Value / Shares Outstanding

所有金额在输出表中都以 百万（M） 为单位。


### 财务指标与增长率（Version C）
### 三阶段 10 年 DCF 增长模型
本项目对每只股票采用 **三阶段 10 年 DCF 模型**：
1. **数据来源**
   - 使用 SEC EDGAR `companyfacts` API 获取历史财务数据：
     - 收入（Revenue）
     - 净利润（Net Income）
     - 经营现金流（CFO）
     - 资本开支（CapEx）
   - 使用公司 `sic` 行业代码，将公司映射到 6 个大类之一：
     - TECH / CONSUMER / BANK / INSURANCE / ENERGY / PHARMA
2. **关键指标计算**
   - 自由现金流：`FCF = CFO - CapEx`
   - 年度净利率：`Net Profit Margin_y = Net Income_y / Revenue_y`
   - 年度 FCF / 净利润比：`FCF_to_NI_y = FCF_y / Net Income_y`
     - 去掉“净利润极小”的年份，避免比例爆炸
     - 将 FCF/NI 限制在 `[-150%, +150%]` 区间
   - 平均净利率、平均 FCF/NI：
     - 取最近 `N=5` 年有效数据的平均值
   - FCF 利润率：
     - `FCF Margin = Avg(Net Margin) * Avg(FCF/NI)`
     - 并限制在 `[-10%, 50%]` 区间
3. **增长率假设（Sector-based）**
   - 先通过 `sic` → sector（例如 TSLA → CONSUMER，AAPL → TECH）。
   - 每个 sector 预定义一组合理的三阶段增长率区间 `SECTOR_GROWTH`：
     - fast（高增长期，Years 1–5）
     - stable（稳定期，Years 6–10）
     - terminal（永续期）
   - 对于具体公司：
     1. 使用分析师预测（`yfinance.earnings_forecasts`）或最近 3–5 年 Revenue CAGR 计算一个基准增长率 `base_g`。
     2. 将 `base_g` 限制在该行业 fast 阶段的区间内，作为第 1–5 年目标增速。
     3. 第 6–10 年逐步向 stable 区间收敛。
     4. 永续增长率在行业 terminal 区间内，并与用户输入的 `perpetual_growth` 保持一致。
4. **DCF 估值**
   - 从最近一个有数据的年度收入 `Revenue_last` 出发，用 10 年增长路径生成未来每年收入：
     - `Revenue_t = Revenue_{t-1} * (1 + g_t)`
   - 用 FCF Margin 转成自由现金流：
     - `FCF_t = Revenue_t * FCF Margin`
   - 用要求回报率 `r` 折现前 10 年现金流：
     - `PV_FCF_t = FCF_t / (1 + r)^t`
   - 在第 10 年之后使用永续增长率 `g_terminal` 计算终值：
     - `Terminal FCF = FCF_10 * (1 + g_terminal)`
     - `Terminal Value = Terminal FCF / (r - g_terminal)`
     - `PV_Terminal = Terminal Value / (1 + r)^10`
   - 企业价值：
     - `Enterprise Value = Σ PV_FCF_t + PV_Terminal`
   - 每股公允价值：
     - `Fair Value / Share = Enterprise Value / Shares Outstanding`




# SEC data structure

{
  "cik": "0001652044", // Central Index Key
  "entityName": "Alphabet Inc.",
  "facts": {
      "<taxonomy>": {
          "<tagName>": {
              "label": "...",
              "description": "...",
              "units": {
                  "<unitName>": [
                      { filing object 1 },
                      { filing object 2 },
                      ...
                  ]
              }
          }
      }
  }
}

<!-- 
facts 字段包含所有财务指标（如 Revenue, NetIncomeLoss, OperatingCashFlow 等), 结构分三层：
❶ taxonomy（分类层）
常见 taxonomy：
"us-gaap" — 美国通用会计准则
"dei" — 公司基本信息
"ifrs-full" — IFRS 公司
"invest" — 投资类
❷ tagName（指标标签层）
例如：
"Revenues"
"RevenueFromContractWithCustomerExcludingAssessedTax"
"NetIncomeLoss"
"OperatingIncomeLoss"
"CashAndCashEquivalentsAtCarryingValue"
每个 tag 包含：
label - 简短名称（可读）
description - 指标描述
例子可从搜索结果看到：
如开始的文本，是一个 tag 的 description。

units - 指标的值，按单位分类
常见单位：
"USD"（绝大多数财务数字）
"shares"
"pure"（百分比比率类）

"units": {
    "USD": [
        {
            "start": "YYYY-MM-DD",      // 会计期间开始（可选）
            "end": "YYYY-MM-DD",        // 会计期间结束（或时间点）
            "val": number,              // 数值
            "accn": "...",              // filing accession number
            "fy": YYYY,                 // fiscal year 财年
            "fp": "Q1/Q2/Q3/Q4/FY",     // fiscal period
            "form": "10-K / 10-Q ...",  // 文件类型：10-K = 美国公司年报（US）, 20-F = 外国公司年报（IFRS）, 40-F = 加拿大公司年报（MJDS）, 10-Q 季度报告, 8-K 临时公告, S-1/F-1 上市申请文件, 6-K 外国公司小型更新
            "filed": "YYYY-MM-DD",      // 提交日期
            "frame": "CY2024Q3"         // XBRL 时间窗口 ID（可选）日历年
        }
    ]
} 



例子
{ "start": "2018-01-01",
              "end": "2018-12-31",
              "val": 136819000000,
              "accn": "0001652044-21-000010", # 
              "fy": 2020, # 这份 filing 是“FY 2020 年报”
              "fp": "FY",
              "form": "10-K", #美国公司年报
              "filed": "2021-02-03", # 这个数据是被“重新提交”（restated）或“在 2020 年年报里包含”并于 2021 年提交
              "frame": "CY2018" # 日历年 2018 的数据
}
-->

