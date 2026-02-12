# Options Trading Guide

> 针对已有股票投资经验、Fidelity Options Tier 1 的投资者

---

## 第一章：期权的本质

### 1.1 一句话理解期权

期权 = **买保险**。你付一笔保费（premium），获得在未来某个日期以约定价格买/卖股票的**权利**。

### 1.2 四个基本角色

| | Call（看涨期权） | Put（看跌期权） |
|---|---|---|
| **买方 (Long)** | 付 premium，获得**买入**股票的权利 | 付 premium，获得**卖出**股票的权利 |
| **卖方 (Short)** | 收 premium，承担**卖出**股票的义务 | 收 premium，承担**买入**股票的义务 |

记住：**买方有权利，卖方有义务**。

### 1.3 关键术语

| 术语 | 含义 | 例子 |
|------|------|------|
| **Strike Price（行权价）** | 约定的买/卖价格 | AVGO $300 put → 行权价 $300 |
| **Expiration（到期日）** | 期权失效的日期 | 2026-03-21 |
| **Premium（权利金）** | 期权的价格 | $5.00/股 = $500/合约 |
| **Contract（合约）** | 1 份合约 = 100 股 | 买 1 张 call = 控制 100 股 |
| **ITM（价内）** | 期权有内在价值 | 股价 $340, call strike $300 → ITM |
| **ATM（平价）** | 行权价 ≈ 当前股价 | 股价 $340, strike $340 |
| **OTM（价外）** | 期权没有内在价值 | 股价 $340, call strike $380 → OTM |

### 1.4 期权价格的组成

```
期权价格 = 内在价值 (Intrinsic Value) + 时间价值 (Time Value)
```

- **内在价值**：如果现在立刻行权能赚多少
  - Call: max(股价 - strike, 0)
  - Put: max(strike - 股价, 0)
- **时间价值**：到期前可能发生变化的"可能性溢价"，随时间流逝递减

**例子**：AVGO 现价 $340
- $300 Call: 内在价值 = $40, 如果 premium = $45, 时间价值 = $5
- $300 Put: 内在价值 = $0 (OTM), 如果 premium = $3, 全部是时间价值

---

## 第二章：The Greeks（希腊字母）

Greeks 衡量期权价格对各种因素的敏感度。**不需要死记公式，理解直觉就够了。**

### 2.1 Delta (Δ) — 方向敏感度

> 股价变动 $1，期权价格变动多少

| Delta 值 | 含义 |
|----------|------|
| Call: +0.5 | 股价涨 $1 → 期权涨 $0.50 |
| Put: -0.3 | 股价涨 $1 → 期权跌 $0.30 |
| Deep ITM: ≈ ±1.0 | 期权价格几乎跟股价 1:1 变动 |
| Deep OTM: ≈ 0 | 股价变动对期权影响很小 |

**实用意义**：Delta ≈ 期权到期时 ITM 的概率。Delta 0.3 的 put ≈ 30% 概率被 assign。

### 2.2 Theta (Θ) — 时间衰减

> 每过一天，期权价值损失多少

- 买方的敌人，卖方的朋友
- ATM 期权 theta 最大
- **最后 30 天加速衰减**
- 例：Theta = -$0.15 → 什么都不变的话，期权每天贬值 $0.15

**实用意义**：卖 put/call 的人靠 theta 赚钱。选 30-45 天到期的合约，theta decay 最有利。

### 2.3 Vega (ν) — 波动率敏感度

> 隐含波动率 (IV) 变动 1%，期权价格变动多少

- 高 IV = 期权贵（恐慌时 put 很贵）
- 低 IV = 期权便宜
- 卖方希望 IV 高（收更多 premium），买方希望 IV 低

**实用意义**：财报前 IV 飙升（期权贵），财报后 IV 暴跌（IV Crush）。不要在财报前买期权。

### 2.4 Gamma (Γ) — Delta 的变化率

> 股价变动 $1，Delta 变动多少

- ATM + 临近到期 → Gamma 最大 → 期权价格变化剧烈
- 卖方最怕高 Gamma（价格突然大幅波动）

### 2.5 Greeks 速查

```
想赚方向的钱  → 看 Delta
想赚时间的钱  → 看 Theta（卖方策略）
想赚波动的钱  → 看 Vega
控制风险      → 看 Gamma
```

---

## 第三章：你能用的策略（Tier 1）

你的 Fidelity Tier 1 权限包括：

| 策略 | 类型 | 风险等级 |
|------|------|---------|
| Buy Calls/Puts | 买方 | 中（最多亏 premium） |
| Sell Covered Calls | 卖方 | 低 |
| Sell Cash-Secured Puts | 卖方 | 中 |
| Long Straddles/Strangles | 买方 | 中 |

### 3.1 Sell Cash-Secured Put（卖现金担保看跌期权）

> **你的 AVGO 场景**：想在 $300 买 AVGO，现在 $340 太贵

**操作**：卖 1 张 AVGO $300 Put，到期日 30-45 天后

**盈亏图**：
```
利润
 ^
 |  premium ────────────────────
 |  收到的    \
 +─────────────\──────────────── 股价
 |              \
 |               \
 |    最大亏损 = (strike - premium) × 100
 |
 └── $0      $300    $340
              strike   现价
```

**两种结果**：

| 到期时 AVGO 价格 | 结果 | 你的收益 |
|-----------------|------|---------|
| > $300 | 期权作废 (expire worthless) | 白赚 premium |
| ≤ $300 | 被 assign，以 $300 买入 100 股 | 实际成本 = $300 - premium |

**选择合约的原则**：
- **到期日**：30-45 天（theta decay 最优）
- **Strike**：你真正愿意买入的价格（不要为了多收 premium 选太高的 strike）
- **Delta**：-0.15 到 -0.30（15-30% 被 assign 概率）
- **需要保证金**：strike × 100 = $30,000（cash-secured）或用 margin

**风险**：如果 AVGO 暴跌到 $200，你仍然以 $300 买入，立刻浮亏 $10,000。**只在你真的想持有这只股票时才卖 put。**

### 3.2 Covered Call（备兑看涨期权）

> 你持有股票，卖出 call 赚额外收入

**适合你的场景**：你持有 89 股 TSLA，可以卖 covered call（不过不满 100 股不行）

**操作**：持有 100 股 XYZ → 卖 1 张 OTM Call

**两种结果**：

| 到期时股价 | 结果 | 你的收益 |
|-----------|------|---------|
| < strike | 期权作废，保留股票 | 股票 + premium |
| ≥ strike | 股票被 call away（卖出） | strike × 100 + premium |

**风险**：股价暴涨超过 strike，你的股票被以 strike 价卖出，错失上涨空间。

**适用场景**：
- 你认为股票短期不会大涨
- 想在持有期间赚额外收入
- 愿意在某个价格卖出

### 3.3 Buy Call（买看涨期权）

> 用小钱博大涨

**操作**：花 $300 买 1 张 AVGO Call

**盈亏**：
- 最大亏损 = $300（premium 归零）
- 最大收益 = 无上限
- 盈亏平衡点 = strike + premium

**注意**：
- 时间在消耗你的 premium（theta 每天扣钱）
- 如果股价不动或小涨，你大概率亏钱
- **胜率低，赔率高**

### 3.4 Buy Put（买看跌期权）

> 给持仓买保险（protective put）

**适用场景**：你重仓 TSLA（60%），担心暴跌

**操作**：买 TSLA $350 Put（假设 TSLA 现价 $417）

**效果**：
- TSLA 跌破 $350 → put 赚钱，对冲持仓亏损
- TSLA 不跌 → premium 亏光，相当于保费白交

**成本**：每月 $500-1000 的"保险费"，长期持有不划算。

### 3.5 Long Straddle / Strangle

> 赌大波动，不赌方向

**Straddle**：同时买 ATM Call + ATM Put（同一 strike）
**Strangle**：买 OTM Call + OTM Put（不同 strike，更便宜）

**适用场景**：财报前预期大波动，但不确定方向

**风险**：如果股价不动，两边都亏（被 theta 和 IV crush 双杀）。**新手慎用。**

---

## 第四章：期权定价直觉

### 4.1 什么让期权更贵？

| 因素 | Call 更贵 | Put 更贵 |
|------|----------|----------|
| 股价上涨 | ✓ | |
| 股价下跌 | | ✓ |
| 波动率上升 (IV↑) | ✓ | ✓ |
| 时间更长 | ✓ | ✓ |
| 利率上升 | ✓ (微弱) | |

### 4.2 IV Rank 和 IV Percentile

- **IV Rank**：当前 IV 在过去一年 IV 范围中的位置（0-100）
- IV Rank > 50 → IV 偏高 → 适合**卖**期权
- IV Rank < 30 → IV 偏低 → 适合**买**期权

### 4.3 隐含波动率 vs 历史波动率

```
隐含波动率 (IV)：市场预期未来的波动（从期权价格反推）
历史波动率 (HV)：过去实际发生的波动

IV > HV → 期权"贵了" → 卖方有优势
IV < HV → 期权"便宜了" → 买方有优势
```

---

## 第五章：实操指南

### 5.1 在 Fidelity 下单流程

1. **Trade → Options**
2. 输入 ticker（如 AVGO）
3. 选择 **Expiration Date**（到期日）
4. 选择 **Strike Price**
5. 选择 Action：
   - Buy to Open = 买入开仓
   - Sell to Open = 卖出开仓
   - Buy to Close = 买入平仓（关闭卖出的仓位）
   - Sell to Close = 卖出平仓（关闭买入的仓位）
6. 选择 Order Type：Limit（限价单，推荐）
7. 价格填 bid 和 ask 之间的中间价
8. Preview Order → Submit

### 5.2 期权链 (Option Chain) 怎么看

```
         CALLS                           PUTS
 Last  Bid   Ask   Vol   OI  | Strike |  Last  Bid   Ask   Vol   OI
 45.2  44.8  45.6  120  3400 |  $300  |  3.10  2.90  3.30   85  5200
 35.0  34.5  35.5   80  2100 |  $310  |  5.40  5.10  5.70   60  3800
 ...                         |  $340  |  ...
```

- **Bid**：你卖出能拿到的价格
- **Ask**：你买入要付的价格
- **Volume (Vol)**：当日成交量 → 越高越好
- **Open Interest (OI)**：未平仓合约数 → 越高流动性越好
- **选 OI > 1000、bid-ask spread 小的合约**

### 5.3 你的 AVGO 卖 Put 实操步骤

```
1. Trade → Options → AVGO
2. Expiration: 选 30-45 天后（如 2026-03-20）
3. Strike: $300
4. Action: Sell to Open
5. Quantity: 1
6. Order Type: Limit
7. Price: 看 $300 put 的 bid 价（比如 $3.00）
8. Preview → 确认保证金要求 → Submit
```

**收到 $300 (= $3.00 × 100)**，然后等到期。

### 5.4 平仓 vs 持有到期

不一定要等到期。你可以随时 **Buy to Close** 平仓：

| 场景 | 操作 | 原因 |
|------|------|------|
| 卖了 put 收 $300，现在只值 $50 | Buy to Close $50 | 赚了 $250，锁定利润 |
| 股价暴跌，put 从 $300 涨到 $1500 | Buy to Close $1500 | 止损，防止被 assign |
| 快到期，不想被 assign | Buy to Close | 避免买入 100 股 |

**经验法则**：当 premium 缩水到原来的 50% 时就平仓，不要为了剩下的 50% 冒额外风险。

---

## 第六章：风险管理

### 6.1 绝对不要做的事

1. **裸卖 Call (Naked Call)** — 亏损无上限（你也没 Tier 权限）
2. **All-in 买期权** — 期权可以归零，永远只用你能承受亏光的钱
3. **财报前买期权** — IV Crush 会让你即使方向对了也亏钱
4. **忽略流动性** — 不要交易 OI < 100 的合约，bid-ask spread 会吃掉你的利润
5. **卖 put 不想持有的股票** — 只为了 premium 卖 put，暴跌时你会被迫买入垃圾

### 6.2 仓位管理

```
单笔期权交易风险 ≤ 账户总值的 2-5%

你的 Y 账户 ~$63K:
  - 单笔最大风险: $1,260 - $3,150
  - 卖 1 张 AVGO $300 put: 最大风险 ~$30,000（极端情况）
    → 占账户 47%，偏高，但如果你真的想持有 AVGO 可以接受
```

### 6.3 卖 Put 的 Wheel Strategy（轮盘策略）

这是最适合你投资风格的策略（长期持有 + 想低价买入）：

```
第 1 步：卖 OTM Put（想买入的价格）
         │
    没被 assign ←──── 到期 ────→ 被 assign
         │                         │
    重复卖 put                  你拥有 100 股
    继续收 premium                  │
                                    ↓
                        第 2 步：卖 OTM Covered Call
                                    │
                          没被 call away ←── 到期 ──→ 被 call away
                                    │                      │
                             继续卖 call               股票卖出
                             收 premium                回到第 1 步
```

**循环赚 premium**：卖 put 收钱 → 被 assign 拿到股票 → 卖 call 收钱 → 被 call away 卖出 → 再卖 put...

---

## 第七章：税务影响（美国）

### 7.1 基本规则

| 持有时间 | 税率 |
|---------|------|
| < 1 年 (Short-term) | 普通收入税率（可能 22-37%） |
| > 1 年 (Long-term) | 优惠税率（0/15/20%） |

### 7.2 期权的税务处理

| 场景 | 税务处理 |
|------|---------|
| 买 call/put → 过期作废 | Capital loss（可抵税） |
| 买 call/put → 卖出平仓 | Short-term capital gain/loss |
| 卖 put → 过期 | Premium = short-term capital gain |
| 卖 put → 被 assign | Premium 降低 cost basis（买入成本减少） |
| 卖 covered call → 过期 | Premium = short-term capital gain |
| 卖 covered call → 被 call away | Premium 加入 sale proceeds |

**注意**：期权收入几乎都是 short-term，税率较高。

### 7.3 Wash Sale Rule

30 天内买回"实质相同"的证券 → 亏损不能抵税。
卖 put 被 assign 可能触发 wash sale（如果你 30 天内刚卖了同一只股票亏损）。

---

## 第八章：实战检查清单

### 开仓前问自己：

- [ ] **方向判断**：我对这只股票的观点是什么？（看涨/看跌/震荡）
- [ ] **策略匹配**：这个策略和我的观点一致吗？
- [ ] **最大亏损**：如果完全判断错误，我最多亏多少？能承受吗？
- [ ] **流动性**：OI > 500? Bid-ask spread < 10%?
- [ ] **IV 水平**：IV Rank 高还是低？适合买还是卖？
- [ ] **到期日**：30-45 天？避开财报日？
- [ ] **仓位大小**：风险 < 账户的 5%？
- [ ] **退出计划**：什么时候止盈？什么时候止损？

### 卖 Put 专用检查清单：

- [ ] 我真的想以这个 strike 买入这只股票吗？
- [ ] 如果被 assign，我有足够的资金/margin 吗？
- [ ] 如果股价跌 30%，我还愿意持有吗？
- [ ] 最近有财报吗？（财报前卖 put 风险大）

---

## 附录：常用期权缩写

| 缩写 | 全称 | 含义 |
|------|------|------|
| BTO | Buy to Open | 买入开仓 |
| STO | Sell to Open | 卖出开仓 |
| BTC | Buy to Close | 买入平仓 |
| STC | Sell to Close | 卖出平仓 |
| CSP | Cash-Secured Put | 现金担保看跌期权 |
| CC | Covered Call | 备兑看涨期权 |
| IV | Implied Volatility | 隐含波动率 |
| HV | Historical Volatility | 历史波动率 |
| OI | Open Interest | 未平仓合约数 |
| DTE | Days to Expiration | 距到期天数 |
| ATM/ITM/OTM | At/In/Out of the Money | 平价/价内/价外 |
| P/L | Profit and Loss | 盈亏 |

---

## 推荐学习路径

```
Week 1:  理解第1-2章 → 在 Fidelity 看 option chain 但不下单
Week 2:  模拟交易（Fidelity 没有纸盘，用 thinkorswim paper trading）
Week 3:  第一笔真实交易 → 卖 1 张 CSP（选你真的想买的股票）
Week 4+: 复盘，学习第4-6章，逐步加入 covered call
```

**第一笔交易建议**：卖 1 张你想买的股票的 OTM put，30-45 DTE，delta -0.20。
用你的 AVGO $300 put 场景练手就很好。

---

*Generated: 2026-02-10*
