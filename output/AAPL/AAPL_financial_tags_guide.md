# AAPL SEC EDGAR XBRL 数据指南

以 Apple Inc. (AAPL) 为例，解释我们从 SEC 财报中提取了哪些数据、它们是什么意思、怎么看、有什么坑。

> 数据来源：SEC EDGAR companyfacts API (`https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json`)

---

## 目录

1. [三张报表概览](#1-三张报表概览)
2. [我们提取的指标详解](#2-我们提取的指标详解)
3. [派生指标（算出来的）](#3-派生指标算出来的)
4. [XBRL Tag 切换问题](#4-xbrl-tag-切换问题)
5. [时间点 vs 时间段数据](#5-时间点-vs-时间段数据)
6. [AAPL 财年特殊性](#6-aapl-财年特殊性)
7. [Shares Outstanding 的跳变](#7-shares-outstanding-的跳变)
8. [AAPL 还有哪些有意思的 Tag](#8-aapl-还有哪些有意思的-tag)
9. [看报表的 Checklist](#9-看报表的-checklist)

---

## 1. 三张报表概览

公司财报由三张核心报表组成，它们之间互相关联：

```
┌─────────────────────────────────────────────────────────────┐
│                    Income Statement (利润表)                 │
│            "这段时间赚了多少钱"（时间段数据）                    │
│  Revenue → Gross Profit → Operating Income → Net Income      │
│       ↓ (Net Income 流入 Retained Earnings)                  │
├─────────────────────────────────────────────────────────────┤
│                    Balance Sheet (资产负债表)                  │
│          "在某一天拥有什么、欠什么"（时间点数据）                  │
│  Assets = Liabilities + Stockholders' Equity                 │
│       ↓ (Cash 变动需要解释)                                   │
├─────────────────────────────────────────────────────────────┤
│                   Cash Flow Statement (现金流量表)             │
│            "现金从哪来、到哪去"（时间段数据）                    │
│  CFO (经营) + CFI (投资) + CFF (融资) = Cash 变动             │
└─────────────────────────────────────────────────────────────┘
```

**关键理解**：利润 ≠ 现金。公司可以"盈利"但没有现金（应收账款多），也可以"亏损"但现金充裕（折旧是非现金费用）。

---

## 2. 我们提取的指标详解

### 利润表 (Income Statement) — 时间段数据

| 指标 | XBRL Tag | 单位 | 含义 |
|------|----------|------|------|
| **Revenue** | `RevenueFromContractWithCustomerExcludingAssessedTax` | USD | 总营收。公司卖东西/提供服务赚的钱 |
| **Gross Profit** | `GrossProfit` | USD | 毛利润 = Revenue - COGS（销售成本）。反映产品本身赚不赚钱 |
| **Net Income** | `NetIncomeLoss` | USD | 净利润 = 扣除所有费用、税、利息后的最终利润 |
| **EPS Diluted** | `EarningsPerShareDiluted` | USD/shares | 稀释后每股收益 = Net Income / 稀释后总股数 |

**AAPL 实际数据 (FY2025)**：
- Revenue: $416.2B → Gross Profit: $195.2B (毛利率 46.9%) → Net Income: $112.0B (净利率 26.9%)
- 意味着 AAPL 每赚 $1 营收，$0.47 是毛利，最终 $0.27 变成净利润

**Gross Margin（毛利率）怎么看**：
- 我们的公式：`Gross Margin = GrossProfit / Revenue × 100%`
- AAPL 毛利率从 2007 年的 34% 涨到 2025 年的 47% — 说明产品定价能力和产品组合在改善（服务收入占比提高，服务毛利率远高于硬件）
- 对比：硬件公司通常 30-40%，软件/服务公司 60-80%

**Net Profit Margin（净利率）怎么看**：
- 我们的公式：`Net Margin = NetIncome / Revenue × 100%`
- AAPL 净利率 21-27% 非常高且稳定，说明运营效率好、规模经济强
- 如果一家公司毛利率高但净利率低 → 运营费用（SGA、R&D）太高

**EPS Diluted（稀释后每股收益）怎么看**：
- "稀释后"意味着把所有可能变成股票的东西（期权、RSU、可转债）都算进去
- 这是投资者最常看的盈利指标之一
- AAPL 2025: $7.46/share — 如果股价 $240，则 P/E = 240/7.46 ≈ 32 倍
- ⚠ 注意：AAPL 在 2014 年做了 7:1 拆股、2020 年做了 4:1 拆股，导致 EPS 历史数据有跳变

---

### 现金流量表 (Cash Flow Statement) — 时间段数据

| 指标 | XBRL Tag | 单位 | 含义 |
|------|----------|------|------|
| **CFO** | `NetCashProvidedByUsedInOperatingActivities` | USD | 经营活动产生的现金流。核心业务"真正"赚到的现金 |
| **CapEx** | `PaymentsToAcquirePropertyPlantAndEquipment` | USD | 资本支出。购买固定资产（设备、厂房、数据中心）花的钱 |

**CFO 怎么看**：
- CFO 从 Net Income 出发，调整非现金项目（折旧加回来）和营运资本变动
- CFO > Net Income → 好信号，说明盈利的"含金量"高
- AAPL FY2025: CFO $111.5B vs Net Income $112.0B → 几乎 1:1，非常健康
- 如果 CFO << Net Income → 可能有应收账款堆积、存货积压等问题

**CapEx 怎么看**：
- CapEx 是现金流量表投资活动里的一项支出
- 它是"现金支出"而不是"费用" — 花了真金白银但不直接减少利润（通过折旧逐年分摊到利润表）
- AAPL FY2025: $12.7B — 用于建设数据中心、零售店、生产设备等
- CapEx / Revenue = 3.1% → 算轻资产公司（重资产如半导体 15-25%）
- CapEx 高 → 公司在扩张，未来产能/能力会提升，但短期现金流承压

**CapEx 的来源**：
- AAPL 早年(2007-2012)用的 tag 是 `PaymentsToAcquireProductiveAssets`（更广义，包含无形资产）
- 2013年起切换到 `PaymentsToAcquirePropertyPlantAndEquipment`（仅 PP&E，更精确）
- 两者区别不大，但严格来说后者不包含购买专利、版权等无形资产的支出

---

### 资产负债表 (Balance Sheet) — 时间点数据

| 指标 | XBRL Tag | 单位 | 含义 |
|------|----------|------|------|
| **Cash** | `CashAndCashEquivalentsAtCarryingValue` | USD | 现金及等价物。银行存款 + 3个月内到期的高流动性投资 |
| **Marketable Securities (Current)** | `MarketableSecuritiesCurrent` | USD | 短期有价证券。1年内到期的国债、公司债等 |
| **Marketable Securities (Noncurrent)** | `MarketableSecuritiesNoncurrent` | USD | 长期有价证券。1年以上到期的债券投资 |
| **Long-term Debt** | `LongTermDebt` / `LongTermDebtNoncurrent` | USD | 长期债务。1年后到期的借款/债券 |
| **Short-term Debt** | `CommercialPaper` | USD | 短期债务。AAPL 主要通过商业票据(CP)短期融资 |
| **Shares Outstanding** | `CommonStockSharesOutstanding` | shares | 流通在外的普通股总数 |

**Cash（现金）怎么看**：
- AAPL FY2025: Cash $35.9B — 这只是"马上能用的钱"
- 但 AAPL 还有大量有价证券投资

**Total Cash（总现金储备）怎么看**：
- 我们的公式：`Total Cash = Cash + Marketable Securities Current + Marketable Securities Noncurrent`
- AAPL FY2025: $35.9B + $23.0B + $73.5B = $132.4B
- 2019年高达 $205.9B，之后逐年减少 → 因为 AAPL 在大量回购股票 + 还债
- ⚠ 并非所有公司都有 MarketableSecurities 这个 tag，很多公司只有 Cash

**Total Debt（总债务）怎么看**：
- 我们的公式：`Total Debt = Long-term Debt + Short-term Debt`
- AAPL FY2025: $98.7B — 虽然看起来很高，但 Total Cash $132.4B > Total Debt $98.7B
- Net Debt = Total Debt - Total Cash = -$33.7B → 负数表示"净现金"公司，非常健康
- ⚠ AAPL 的短期债务用的是 `CommercialPaper`（商业票据），不是所有公司都这样

**Shares Outstanding（流通股）怎么看**：
- AAPL 从 2013 年的 8.99 亿股增长到 2014 年的 62.9 亿股 → 这是 2014 年 7:1 拆股
- 然后从 2019 年的 44.4 亿股跳到 2020 年的 169.8 亿股 → 这是 2020 年 4:1 拆股
- 拆股后整体趋势是下降的（147.7 亿 in FY2025）→ 因为 AAPL 持续回购股票
- 拆股不改变公司价值，但会让 EPS 看起来变小（EPS 也按拆股后调整了）

---

## 3. 派生指标（算出来的）

这些指标不直接从 SEC 提取，是我们用上面的原始数据计算的：

| 指标 | 公式 | 含义 |
|------|------|------|
| **Free Cash Flow (FCF)** | CFO - CapEx | 自由现金流。公司运营赚到的现金减去维持/扩展业务必须花的钱，剩下的可以自由支配（分红、回购、收购、还债） |
| **Gross Margin %** | Gross Profit / Revenue × 100 | 毛利率。每 $1 营收中毛利占多少 |
| **Net Profit Margin %** | Net Income / Revenue × 100 | 净利率。每 $1 营收最终变成多少净利润 |
| **FCF to Profit Margin %** | FCF / Net Income × 100 | 盈利的"含金量"。净利润有多少真正变成了可自由支配的现金 |
| **Total Cash** | Cash + MS Current + MS Noncurrent | 总现金储备。所有可以快速变现的金融资产 |
| **Total Debt** | LT Debt + ST Debt | 总债务 |

**FCF 怎么看**：
- AAPL FY2025: FCF $98.8B — 这是 AAPL 一年真正"赚到手"的现金
- FCF 是 DCF 估值的核心输入 — 公司的价值 = 未来所有 FCF 的折现值
- FCF 持续增长 → 公司价值在增加
- ⚠ 高成长公司 (如 TSLA) FCF 可能很低甚至为负，因为 CapEx 巨大（在建工厂）

**FCF to Profit Margin 怎么看**：
- \> 100% → 非现金费用（折旧）大于营运资本消耗，现金流比利润还多
- < 100% → 有部分利润被营运资本吃掉了（应收增加、存货增加等）
- AAPL FY2025: 88.2% — 略低于 100%，正常范围
- ⚠ 我们把这个值限制在 [-150%, 150%] 区间，避免净利润很小时比率爆炸

---

## 4. XBRL Tag 切换问题

这是看 SEC 数据最大的坑之一。**同一个指标，不同年份可能用不同的 XBRL tag 报告**。

### AAPL 实际发生的 Tag 切换

| 指标 | 早期 Tag | 切换年份 | 新 Tag | 原因 |
|------|---------|---------|--------|------|
| Revenue | `SalesRevenueNet` | 2016→2017 | `Revenues` → `RevenueFromContractWithCustomerExcludingAssessedTax` | FASB 会计准则更新 (ASC 606) |
| CapEx | `PaymentsToAcquireProductiveAssets` | 2012→2013 | `PaymentsToAcquirePropertyPlantAndEquipment` | 自愿细化披露 |
| LT Debt | `LongTermDebt` | 2015→2016 | `LongTermDebtNoncurrent` → 2024 回到 `LongTermDebt` | 披露偏好变动 |
| CFO | `NetCashProvidedByUsedInOperatingActivities` | FY2014 | `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` | 一年用了不同 tag |
| Shares | `WeightedAverageNumberOfSharesOutstandingBasic` | 2007→2009 | `CommonStockSharesOutstanding` | 不同口径 |

### 为什么会切换？

1. **会计准则更新**：FASB 发布新准则（如 ASC 606 收入确认），公司必须改用新 tag
2. **公司自愿细化**：从宽泛 tag 切到更精确的 tag
3. **披露方式调整**：同一概念有多个合法 tag，公司换了个说法

### 我们怎么处理的？

在 `_series_from_tags()` 中，我们按优先级列表尝试所有可能的 tag，然后**按优先级合并**：
- 如果 2017 年同时有 `Revenues` 和 `RevenueFromContractWithCustomerExcludingAssessedTax` 的数据，取优先级更高的
- 这样就能拼出完整的历史时间线

### Tag 行的作用

10K 输出中每个指标都有对应的 Tag 行（如 `Revenue Tag`, `CFO Tag`），记录每年实际用了哪个 tag。如果你发现某年数据异常，先看 tag 有没有切换。

---

## 5. 时间点 vs 时间段数据

这是理解财报数据的核心概念：

### 时间段数据 (Period / Flow)
- **哪些**：Revenue, Net Income, CFO, CapEx, Gross Profit, EPS
- **含义**：从 Start 到 End 这段时间内的累计值
- **XBRL 字段**：有 `start` 和 `end`，如 `start: 2024-09-29, end: 2025-09-27`
- **例子**：AAPL FY2025 Revenue = $416.2B 是从 2024-09-29 到 2025-09-27 这一年的总营收

### 时间点数据 (Point-in-time / Stock)
- **哪些**：Cash, Debt, Assets, Equity, Shares Outstanding
- **含义**：在某一天的余额/快照
- **XBRL 字段**：只有 `end`（报告日期），没有 `start`
- **例子**：AAPL Cash = $35.9B 是在 2025-09-27 这一天的现金余额

### 为什么这很重要？

1. **不能跨公司直接比较时间段数据**，除非它们的财年对齐（AAPL 财年 10月-9月，MSFT 7月-6月）
2. **时间点数据可能同一年有多个值**（年报一个、季报一个），我们只取年度值
3. **Start/End 行**帮你确认数据覆盖的实际时间段

---

## 6. AAPL 财年特殊性

**AAPL 的财年不是自然年！**

- AAPL 的财年结束于 **9月最后一个周六**（不固定日期）
- FY2025 = 2024-09-29 到 2025-09-27
- 所以我们标注的 "2025" 列，实际上覆盖的是 2024年10月到2025年9月

这意味着：
- AAPL 的 FY2025 和 GOOGL 的 FY2025（日历年 1月-12月）时间不完全重叠
- 如果你要比较两家公司的季度数据，要注意对齐
- AAPL 每年通常在 **10月底** 发布年报 (10-K)

### 其他公司的财年

| 公司 | 财年结束月 | 标注 "2025" 实际覆盖 |
|------|-----------|---------------------|
| AAPL | 9月 | 2024.10 - 2025.9 |
| MSFT | 6月 | 2024.7 - 2025.6 |
| GOOGL | 12月 | 2025.1 - 2025.12 |
| TSLA | 12月 | 2025.1 - 2025.12 |
| WMT | 1月 | 2024.2 - 2025.1 |

---

## 7. Shares Outstanding 的跳变

AAPL 的 Shares Outstanding 数据有几次大跳变：

```
2013:    899M
2014:  6,294M  ← 7:1 拆股 (899 × 7 = 6,293)
...
2019:  4,443M
2020: 16,977M  ← 4:1 拆股 (4,443 × 4 = 17,772，差异来自回购)
...
2025: 14,773M
```

### 拆股 (Stock Split) 要知道的

1. **不改变公司价值** — 蛋糕大小不变，只是切成更多份
2. **EPS 会按拆股调整** — SEC 要求重新表述历史 EPS，所以看起来连续
3. **每股价格下降** — $700/share 拆 7:1 变成 $100/share
4. **目的**：让散户买得起，提高流动性

### 两种 Shares 口径

| Tag | 含义 | AAPL 使用情况 |
|-----|------|-------------|
| `CommonStockSharesOutstanding` | 资产负债表上的实际流通股数（时间点） | 2009 年起 |
| `WeightedAverageNumberOfSharesOutstandingBasic` | 利润表用的加权平均股数（时间段） | 仅 2007-2008 |

加权平均考虑了年中的回购/发行，所以可能和年末实际流通数略有差异。

---

## 8. AAPL 还有哪些有意思的 Tag

以下是 AAPL 在 SEC 报告但我们目前没提取的一些有用指标：

### 利润表相关

| Tag | 含义 | 投资分析用途 |
|-----|------|-------------|
| `ResearchAndDevelopmentExpense` | 研发费用 | R&D / Revenue 衡量公司对未来的投入 |
| `SellingGeneralAndAdministrativeExpense` | 销售管理费用 | 运营效率的另一指标 |
| `OperatingIncomeLoss` | 营业利润 | = Gross Profit - Operating Expenses，比 Net Income 更反映主营业务 |
| `IncomeTaxExpenseBenefit` | 所得税 | 有效税率 = Tax / Pre-tax Income |
| `CostOfGoodsAndServicesSold` | 销售成本 (COGS) | Revenue - COGS = Gross Profit |
| `CommonStockDividendsPerShareDeclared` | 每股股息 | 分红率 = DPS / EPS |

### 资产负债表相关

| Tag | 含义 | 投资分析用途 |
|-----|------|-------------|
| `Assets` | 总资产 | ROA = Net Income / Assets |
| `StockholdersEquity` | 股东权益 | ROE = Net Income / Equity，衡量股东资本回报率 |
| `PropertyPlantAndEquipmentNet` | 固定资产净值 | 追踪 CapEx 累积效果 |
| `AccountsReceivableNetCurrent` | 应收账款 | 增长过快可能暗示回款困难 |
| `RetainedEarningsAccumulatedDeficit` | 留存收益 | 公司历年积累的未分配利润 |
| `Goodwill` | 商誉 | 收购溢价，如果被减值说明收购失败 |
| `DebtInstrumentCarryingAmount` | 长期债务总额（面值） | 和 LongTermDebt 区别：这个是面值，LongTermDebt 是账面价值 |

### 现金流相关

| Tag | 含义 | 投资分析用途 |
|-----|------|-------------|
| `PaymentsForRepurchaseOfCommonStock` | 股票回购支出 | AAPL 每年花 $700-900亿 回购 |
| `PaymentsOfDividendsCommonStock` | 股息支付 | 和回购一起构成股东回报 |
| `ShareBasedCompensation` | 股权激励费用 | 非现金费用，但会稀释股权。科技公司这项通常很大 |
| `ProceedsFromIssuanceOfLongTermDebt` | 发行长期债务 | AAPL 借债不是因为缺钱，而是利用低利率杠杆 |
| `DepreciationDepletionAndAmortization` | 折旧摊销 (D&A) | 非现金费用，EBITDA = Operating Income + D&A |

---

## 9. 看报表的 Checklist

拿到一家公司的 10K 数据后，按这个顺序检查：

### 第一步：基本面健康度

- [ ] **Revenue 趋势**：是否持续增长？增速如何？
- [ ] **Net Margin**：是否稳定？和同行比如何？
- [ ] **Gross Margin 趋势**：是上升（定价能力增强/产品组合改善）还是下降（竞争加剧/成本上升）？

### 第二步：现金流质量

- [ ] **CFO > Net Income？** 如果是，说明盈利含金量高
- [ ] **FCF 是否为正且增长？** 正的 FCF 是分红/回购/投资的基础
- [ ] **CapEx / Revenue**：了解资本密度。< 5% 轻资产，> 15% 重资产

### 第三步：资产负债表安全性

- [ ] **Net Debt = Total Debt - Total Cash**：负数最好（净现金公司）
- [ ] **Debt / Equity**：杠杆率，太高有风险
- [ ] **Cash 趋势**：在增还是在减？为什么？

### 第四步：数据质量

- [ ] **检查 Tag 行**：有没有 tag 切换导致数据不连续？
- [ ] **检查 Start/End**：财年是否对齐？有没有异常短/长的报告期？
- [ ] **Shares 跳变**：有没有拆股/合股导致的不连续？
- [ ] **空值**：有些年份可能没有数据（公司还没上市/还没用某个 tag）

### 第五步：相对估值（需要股价数据）

- [ ] **P/E = Price / EPS**：和历史平均、同行比
- [ ] **P/S = Market Cap / Revenue**：对于亏损公司用这个
- [ ] **EV/EBITDA**：扣除资本结构影响的估值指标

---

## 附录：AAPL 完整数据一览 (FY2025)

```
Revenue:           $416.2B     毛利率:  46.9%
Net Income:        $112.0B     净利率:  26.9%
CFO:               $111.5B     EPS:     $7.46
CapEx:              $12.7B     FCF:    $98.8B

Cash:               $35.9B     (CashAndCashEquivalentsAtCarryingValue)
Total Cash:        $132.4B     (Cash + 有价证券)
Total Debt:         $98.7B     (LT + ST Debt)
Net Debt:          -$33.7B     ← 净现金公司

Shares:         14,773M 股
财年:           2024-09-29 至 2025-09-27
```
