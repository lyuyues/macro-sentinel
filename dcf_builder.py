#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# dcf_builder.py  美股单只股票 DCF 估值工具
# A lightweight DCF builder that reproduces two valuation tables similar to your spreadsheets.
# It uses SEC EDGAR companyfacts (XBRL) to pull Revenue/Net Income/CFO/CapEx, computes FCF and margins,
# adopts analyst revenue growth via yfinance if available (optional), otherwise falls back to a 3Y CAGR.
# Then it projects 4 years of FCF and discounts them plus a terminal value.
#
# Usage example:
#   python dcf_builder.py --ticker GOOGL --required 0.07 --perp 0.025 --avg-years 5
#
# Outputs in current folder:
#   <YEAR>_dcf_<TICKER>.csv            # historical table
#   <YEAR>_dcf_<TICKER>_proj.csv       # projection + DCF table
#   <YEAR>_dcf_<TICKER>_meta.json      # summary (fair value, assumptions)

# 数据来源
# 	•	SEC EDGAR companyfacts API
# 	•	先通过 https://www.sec.gov/files/company_tickers.json 找到公司对应的 CIK
# 	•	再通过 https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json 拉取 XBRL 明细
# 	•	可选：yfinance 分析师预测
# 	•	若可用，使用 yfinance 的 earnings_forecasts 里的 revenue growth 作为未来增长率
# 	•	否则回退到最近 3–5 年的 Revenue CAGR
# 标准 10 年三阶段 DCF 模型
# 	•	第 1 阶段：快速增长期（Years 1–5）
# 	•	第 2 阶段：稳定期（Years 6–10）
# 	•	第 3 阶段：永续增长（Perpetual）

import argparse, json, math, sys
from typing import Dict, Tuple, Optional
import pandas as pd
import numpy as np
import requests
from pprint import pprint
from typing import Dict, Tuple, Optional, List

from dcf_utils import get_latest_price_stooq, map_sic_to_sector,infer_sector_from_facts,is_true_annual_period



"""
# =======================================
        Module organization
# =======================================
This file is organized into three logical sections to make it easier to read and
maintain:

  1) Fetch layer: functions that call external services (SEC, Stooq) and
      flatten companyfacts JSON (`fetch_cik`, `fetch_companyfacts`,
      `companyfacts_to_table`, `fetch_company_data`).

  2) Decision layer: helpers that parse XBRL tags/periods and choose which
      series/tags to use (`_series_from_tags`, `extract_financials`,
      `adopt_growth_rate`, `infer_sector_from_facts` in dcf_utils).

  3) Calculation layer: pure-ish functions that compute margins, fcf margins,
      growth paths and perform DCF math (`compute_margins`,
      `compute_fcf_margin`, `build_growth_curve`, `build_dcf`).

The goal of this minimal refactor is to separate responsibilities and make the
main `build_dcf` flow easier to follow.
"""

# =======================================
# 数据自定义区
# =======================================
SEC_HEADERS = {"User-Agent": "dcf-builder (email@example.com)"}
SECTOR_GROWTH = {
    "TECH":      {"fast": (0.12, 0.25), "stable": (0.05, 0.10), "terminal": (0.02, 0.03)},
    "CONSUMER":  {"fast": (0.03, 0.10), "stable": (0.02, 0.04), "terminal": (0.015, 0.025)},
    "BANK":      {"fast": (0.02, 0.06), "stable": (0.01, 0.04), "terminal": (0.01, 0.02)},
    "INSURANCE": {"fast": (0.00, 0.05), "stable": (0.00, 0.03), "terminal": (0.01, 0.02)},
    "ENERGY":    {"fast": (-0.03, 0.08), "stable": (0.01, 0.03), "terminal": (0.01, 0.02)},
    "PHARMA":    {"fast": (0.05, 0.12), "stable": (0.03, 0.06), "terminal": (0.02, 0.02)},
}
REVENUE_TAGS = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueServicesNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "ContractRevenue",
        "ServiceRevenue",
        "OperatingRevenue",
        "OilAndGasRevenue",
        "ElectricUtilityRevenue",
        "RealEstateRevenue",
        "FinancialServicesRevenue",
        "InterestAndDividendIncomeOperating",
        "PremiumsEarned",
        "NetInvestmentIncome",
]
NET_INCOME_TAGS = [
    "NetIncomeLoss",
    "ProfitLoss",
]
CFO_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]
CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "CapitalExpendituresInvestments",
    "PaymentsToAcquireProductiveAssets",
]
SHARE_OUTSTANDING_TAGS = [
    "CommonStockSharesOutstanding",
    "EntityCommonStockSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
    "WeightedAverageNumberOfDilutedSharesOutstanding"
]
GROSS_PROFIT_TAGS = [
    "GrossProfit",
]
EPS_DILUTED_TAGS = [
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
]
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsAndShortTermInvestments",
    "Cash",
]
LONG_TERM_DEBT_TAGS = [
    "LongTermDebt",
    "LongTermDebtNoncurrent",
    "LongTermDebtAndCapitalLeaseObligations",
]
SHORT_TERM_DEBT_TAGS = [
    "ShortTermBorrowings",
    "CommercialPaper",
    "LongTermDebtCurrent",
]
TOTAL_ASSETS_TAGS = [
    "Assets",
]
STOCKHOLDERS_EQUITY_TAGS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
OPERATING_INCOME_TAGS = [
    "OperatingIncomeLoss",
]
DA_TAGS = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "Depreciation",
]
INTEREST_EXPENSE_TAGS = [
    "InterestExpense",
    "InterestExpenseDebt",
]
INCOME_TAX_TAGS = [
    "IncomeTaxExpenseBenefit",
]
INCOME_BEFORE_TAX_TAGS = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
]
DIVIDENDS_PER_SHARE_TAGS = [
    "CommonStockDividendsPerShareDeclared",
    "CommonStockDividendsPerShareCashPaid",
]


# =======================================
#  Fetch layer: external I/O functions
# =======================================

# ticker -》 cik
def fetch_cik(ticker: str) -> str:
    # pprint(f"Fetching CIK for ticker {ticker}...")
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=SEC_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    ticker_u = ticker.upper()
    for _, v in data.items():
        if v.get("ticker","").upper() == ticker_u:

            return str(v["cik_str"]).zfill(10)
    raise ValueError(f"Unable to find CIK for ticker {ticker}")

# ticker -> companyfacts JSON
def fetch_companyfacts(cik: str) -> dict:
    print(f"Fetching companyfacts for CIK {cik}...")
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    r = requests.get(url, headers=SEC_HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()

# companyfacts JSON -> pandas DataFrame for further processing
def companyfacts_to_table(facts: dict) -> pd.DataFrame:
    """
    将 SEC companyfacts JSON 展平为一个 pandas DataFrame。
    每一行 = 某个 tag 在某个 unit 下的一条披露记录。
    """
    cik = facts.get("cik")
    entity_name = facts.get("entityName")
    facts_block = facts.get("facts", {})

    rows = []

    for taxonomy, tags in facts_block.items():          # 比如 "us-gaap", "dei"
        for tag, info in tags.items():                  # 比如 "Revenues", "NetIncomeLoss"
            label = info.get("label")
            units = info.get("units", {})

            for unit, items in units.items():           # 比如 "USD", "shares"
                for it in items:                        # 每条披露记录
                    rows.append({
                        "cik": cik,
                        "entityName": entity_name,
                        "taxonomy": taxonomy,
                        "tag": tag,
                        "label": label,
                        "unit": unit,
                        "val": it.get("val"),
                        "fy": it.get("fy"),
                        "fp": it.get("fp"),
                        "form": it.get("form"),
                        "start": it.get("start"),
                        "end": it.get("end"),
                        "filed": it.get("filed"),
                        "accn": it.get("accn"),
                        "frame": it.get("frame"),
                    })

    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["taxonomy", "tag", "fy", "fp", "form", "filed"],
        ignore_index=True
    )
    return df

#   calling function 
def fetch_company_data(ticker: str):
    """High level fetch wrapper.

    Returns (cik, facts) for the given ticker. Keeping this wrapper lets the
    build_dcf flow call a single function for external I/O and makes testing
    easier (mock this function in tests).
    """
    cik = fetch_cik(ticker)
    facts = fetch_companyfacts(cik)
    return cik, facts

# =======================================
#  Decision layer: tag/period selection helpers
# =======================================

#   extract shares outstanding time series
def extract_shares_outstanding(facts):
    share_outstanding_tags = SHARE_OUTSTANDING_TAGS
    s, _tag, _periods = _series_from_tags(facts, share_outstanding_tags, unit="shares")
    return s.sort_index()

#   extract all financial time series into a dict
def extract_all_financials(facts: dict) -> dict:
    """Extract all financial time series from companyfacts.

    Returns dict mapping metric name to (series, tag, periods) tuple.
    """
    result = {}

    # USD metrics (income statement / cash flow / balance sheet)
    for name, tags in [
        ("revenue", REVENUE_TAGS),
        ("net_income", NET_INCOME_TAGS),
        ("cfo", CFO_TAGS),
        ("capex", CAPEX_TAGS),
        ("gross_profit", GROSS_PROFIT_TAGS),
        ("operating_income", OPERATING_INCOME_TAGS),
        ("da", DA_TAGS),
        ("interest_expense", INTEREST_EXPENSE_TAGS),
        ("income_tax", INCOME_TAX_TAGS),
        ("income_before_tax", INCOME_BEFORE_TAX_TAGS),
        ("cash", CASH_TAGS),
        ("long_term_debt", LONG_TERM_DEBT_TAGS),
        ("short_term_debt", SHORT_TERM_DEBT_TAGS),
        ("total_assets", TOTAL_ASSETS_TAGS),
        ("stockholders_equity", STOCKHOLDERS_EQUITY_TAGS),
    ]:
        s, tag, periods = _series_from_tags(facts, tags, unit="USD")
        result[name] = (s, tag, periods)

    # Per-share metrics (USD/shares)
    for name, tags in [
        ("eps_diluted", EPS_DILUTED_TAGS),
        ("dividends_per_share", DIVIDENDS_PER_SHARE_TAGS),
    ]:
        s, tag, periods = _series_from_tags(facts, tags, unit="USD/shares")
        result[name] = (s, tag, periods)

    # Share counts (shares)
    s, tag, periods = _series_from_tags(facts, SHARE_OUTSTANDING_TAGS, unit="shares")
    result["shares_outstanding"] = (s, tag, periods)

    # Derived: FCF = CFO - CapEx
    cfo = result["cfo"][0]
    capex = result["capex"][0]
    idx = cfo.index.union(capex.index)
    fcf = cfo.reindex(idx) - capex.reindex(idx)
    fcf.name = "FreeCashFlow"
    result["fcf"] = (fcf, None, {})

    # Derived: Total Debt = Long Term + Short Term
    ltd = result["long_term_debt"][0]
    std = result["short_term_debt"][0]
    idx = ltd.index.union(std.index)
    total_debt = ltd.reindex(idx).fillna(0) + std.reindex(idx).fillna(0)
    total_debt.name = "TotalDebt"
    result["total_debt"] = (total_debt, None, {})

    # Derived: EBITDA = Operating Income + D&A
    oi = result["operating_income"][0]
    da = result["da"][0]
    idx = oi.index.union(da.index)
    ebitda = oi.reindex(idx).fillna(0) + da.reindex(idx).fillna(0)
    ebitda.name = "EBITDA"
    result["ebitda"] = (ebitda, None, {})

    return result


#   extract financial time series — backward-compatible wrapper
def extract_financials(facts: dict):
    """Original 11-tuple interface for backward compatibility with build_dcf / dcf_screener."""
    data = extract_all_financials(facts)

    revenue, revenue_tag, revenue_periods = data["revenue"]
    net_income, net_income_tag, net_income_periods = data["net_income"]
    _, cfo_tag, cfo_periods = data["cfo"]
    _, capex_tag, capex_periods = data["capex"]
    fcf = data["fcf"][0]

    return (
        revenue,
        net_income,
        fcf,
        revenue_tag,
        net_income_tag,
        cfo_tag,
        capex_tag,
        revenue_periods,
        net_income_periods,
        cfo_periods,
        capex_periods,
    )

#  Helper Function: extract "年度年份" from single XBRL item
def parse_fiscal_year_from_item(item: dict) -> Optional[int]:
    """
    从单条 XBRL 披露记录里，尽量安全地解析出“年度年份”。
    只在我们确认它是“年度数据”的时候返回 year（int），否则返回 None。
    判断顺序：
      1) frame 是年度形式：CY2022 / FY2022 -> 直接取 2022
      2) 若有 start / end 且 is_true_annual_period(start, end) 为 True，则用 end.year
      3) 最后兜底用 fy
    """
    from pandas import to_datetime
    import re

    frame = item.get("frame")
    start = item.get("start")
    end = item.get("end")
    fy = item.get("fy")

    # 1) 优先：frame 是严格的年度形式 (CY2022 / FY2022)
    if frame:
        s = str(frame)
        m = re.fullmatch(r"(CY|FY)(19|20)\d{2}", s)
        if m:
            # 例如 CY2022 -> 取最后 4 位
            return int(s[-4:])

        # frame 存在但不是年度形式（如 CY2022Q1）→ 明确是季度，直接拒绝
        # 不再 fallback 到 fy，防止季度数据冒充年度
        return None

    # 2) 次优：有 start / end，并且通过 is_true_annual_period 判定为"真·年度"
    if start and end:
        try:
            if is_true_annual_period(start, end):
                return int(to_datetime(end).year)
        except Exception:
            pass
        # start/end 存在但不是年度区间 → 拒绝，不 fallback 到 fy
        return None

    # 3) 最后兜底：没有 frame 也没有 start/end 时，退回 fy
    if fy is not None:
        try:
            return int(fy)
        except Exception:
            pass

    # 实在不确定，就返回 None，调用方自己丢弃这一条
    return None

#  Helper Function: extract entities/series from multiple possible tags 
def _series_from_tags(facts: dict, tags: List[str], unit: str = "USD") -> Tuple[pd.Series, Optional[str], dict]:
    import re

    all_series = [] # 记录所有可用的 series
    tag_names = [] # 记录对应的 tag 名称
    # per-tag/year periods: { tag: { year: (start,end) }}
    per_tag_periods = {}
    us_gaap = facts.get("facts", {}).get("us-gaap", {}) # 只处理 us-gaap 部分

    for tag in tags:
        tag_info = us_gaap.get(tag) # 某个 tag 的信息
        if not tag_info:
            continue

        units = tag_info.get("units", {}) # 各个单位下的披露数据
        if unit not in units:
            continue

        rows = []
        periods = {}
        for item in units[unit]:
            form = item.get("form", "")
            fp = (item.get("fp") or "").upper()
            start = item.get("start")
            end = item.get("end")

            # 只要年报的 Form
            if form not in ("10-K", "20-F", "40-F"):
                continue

            # fp 一般是 FY / CY / Q1 等，这里可以保守一点：
            if fp not in ("FY", "CY", ""):
                continue

            # 统一用 helper 来解析“年度年份”
            year = parse_fiscal_year_from_item(item)
            if year is None:
                # 这条记录要么是季度，要么期间不完整，就当作不是年度数据丢掉
                continue

            try:
                val = float(item.get("val"))
            except Exception:
                continue

            # record start/end for this year if present
            periods[year] = (item.get("start"), item.get("end"))

            rows.append((year, val))
        if rows:
            s = (
                pd.DataFrame(rows, columns=["year", "value"])
                .drop_duplicates("year")
                .set_index("year")["value"]
                .sort_index()
            )
            s.name = tag
            all_series.append(s)
            tag_names.append(tag)
            per_tag_periods[tag] = periods

    if not all_series:
        return pd.Series(dtype="float64"), None, {}

    # Merge all tags: for each year, use the value from the first (highest
    # priority) tag that has data.  This avoids gaps when a company switches
    # XBRL tags over time (e.g. SalesRevenueNet -> Revenues).
    # tags list order = priority order.
    merged_values = {}   # year -> value
    merged_tags = {}     # year -> tag name that provided the value
    merged_periods = {}  # year -> (start, end)

    # Build a lookup: tag_name -> series
    tag_to_series = {s.name: s for s in all_series}

    for tag in tags:  # iterate in priority order
        if tag not in tag_to_series:
            continue
        s = tag_to_series[tag]
        periods = per_tag_periods.get(tag, {})
        for year in s.index:
            if year not in merged_values:
                merged_values[year] = float(s.loc[year])
                merged_tags[year] = tag
                merged_periods[year] = periods.get(year, (None, None))

    combined = pd.Series(merged_values).sort_index()
    combined.name = merged_tags.get(max(merged_values.keys())) if merged_values else None
    return combined, merged_tags, merged_periods

# =======================================
#  Calculation layer: pure-ish functions
# =======================================

# 1. 计算净利率和 FCF/净利润比例
# 去掉 “净利润几乎为 0” 的年份（否则比值会爆炸）。
# 把 FCF/NI 限制在 [-150%, +150%] 之间，可以以后自己调这个区间。 《〈《〈《〈《〈
def compute_margins(
    revenue: pd.Series,
    net_income: pd.Series,
    fcf: pd.Series,
    avg_years: int = 5,
):
    # ---- 1. 净利率: Net Profit Margin = Net Income / Revenue ----
    common_ni = revenue.index.intersection(net_income.index)
    net_margin = (net_income[common_ni] / revenue[common_ni]).rename("NetMargin")

    # ---- 2. FCF to Profit margin = FCF / Net Income 比例，做一些清洗 + 限制 ----
    common_fcf = fcf.index.intersection(net_income.index)

    ni_for_ratio = net_income[common_fcf].copy()
    fcf_for_ratio = fcf[common_fcf].copy()

    # 2.1 去掉 “净利润绝对值太小” 的年份，防止 1 块钱净利润 / 巨大 FCF 变成几千倍
    # 规则：|Net Income| < 5% * |Revenue| 或者 太接近 0 的年份直接丢掉 
    rev_for_ratio = revenue.reindex(common_fcf)
    tiny_ni_mask = (ni_for_ratio.abs() < (0.05 * rev_for_ratio.abs())) | (ni_for_ratio.abs() < 1e-6)
    ni_for_ratio[tiny_ni_mask] = np.nan
    fcf_for_ratio[tiny_ni_mask] = np.nan

    # 2.2 原始比例
    raw_ratio = (fcf_for_ratio / ni_for_ratio)

    # 2.3 把极端值裁剪在一个合理区间内，比如 -1.5 ~ 1.5（即 -150% ~ 150%《〈《〈《〈《〈
    fcf_to_ni = raw_ratio.clip(lower=-1.5, upper=1.5).rename("FCF_to_NI")

    def last_n_avg(s: pd.Series, n: int) -> float:
        s = s.replace([np.inf, -np.inf], np.nan).dropna().tail(n)
        return float(s.mean()) if not s.empty else float("nan")

    avg_net_margin = last_n_avg(net_margin, avg_years)
    avg_fcf_to_ni = last_n_avg(fcf_to_ni, avg_years)

    return net_margin, fcf_to_ni, avg_net_margin, avg_fcf_to_ni

# 2. 计算 FCF Margin
#  优先级：
#    1）用最近 avg_years 年的 (FCF / Revenue) 清洗平均值
#    2）否则用 avg_net_margin * avg_fcf_to_
def compute_fcf_margin(
    revenue: pd.Series,
    fcf: pd.Series,
    avg_net_margin: float,
    avg_fcf_to_ni: float,
    avg_years: int = 5,
) -> float:
    """Compute the FCF margin to use for projections.

    Priority:
      1) Use recent cleaned average of (FCF / Revenue) (last `avg_years` years)
      2) Else use avg_net_margin * avg_fcf_to_ni
      3) Else fallback to 15%

    The returned margin is clipped to [-10%, 50%].
    """
    fr_all = (fcf / revenue).replace([np.inf, -np.inf], np.nan).dropna()
    fr_tail = fr_all.tail(avg_years)
    if not fr_tail.empty:
        # remove extreme values by clipping to 10%-90% quantiles then take mean
        low_q = fr_tail.quantile(0.10)
        high_q = fr_tail.quantile(0.90)
        fr_clean = fr_tail.clip(lower=low_q, upper=high_q)
        fcf_margin = float(fr_clean.mean())
    elif not (math.isnan(avg_net_margin) or math.isnan(avg_fcf_to_ni)):
        fcf_margin = avg_net_margin * avg_fcf_to_ni
    else:
        fcf_margin = 0.15

    # clamp to reasonable financial bounds
    fcf_margin = max(min(fcf_margin, 0.50), -0.10)
    return fcf_margin

# 3.  采用分析师预测或历史 CAGR 作为收入增长率
def adopt_growth_rate(ticker: str, revenue: pd.Series) -> float:
    growth = None

    # 1）尝试 yfinance 分析师预测
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        ef = t.earnings_forecasts
        if ef is not None and "revenueEstimate" in ef:
            g = ef["revenueEstimate"].get("growth")
            if isinstance(g, str) and g.endswith("%"):
                growth = float(g.strip("%")) / 100.0
            elif g is not None:
                growth = float(g)
    except Exception:
        growth = None

    # 2）fallback：最近 3–5 年 Revenue CAGR
    if growth is None:
        rev = revenue.dropna().tail(5)
        if len(rev) >= 2 and rev.iloc[0] > 0:
            n = len(rev) - 1
            growth = (rev.iloc[-1] / rev.iloc[0]) ** (1 / n) - 1.0

    # 3）最后兜底一个保守值
    if growth is None:
        growth = 0.05

    # 4）给最终增长率加一个合理的区间限制
    # 比如：-10% ~ +25% 之间，避免 100% 这种长期不现实的增速
    growth = max(min(growth, 0.25), -0.10)

    return growth

# ============================
#  三阶段增长路径：10 年 + 永续 （根据行业估计10年的growth rate）
# ============================
def build_growth_curve(
    ticker: str,
    facts: dict,
    revenue: pd.Series,
    perpetual_growth: float,
    avg_years: int = 5,
) -> Tuple[list, float]:
    """
    返回：
        growth_path: 长度 10 的 list, 每一年对应的收入增长率
        terminal_g:  永续增长率（会结合 sector 范围修正）
    逻辑：
        1. 先用 adopt_growth_rate 得到一个“基准增长率” base_g
        2. 用 SIC → sector, 从 SECTOR_GROWTH 里取 fast/stable/terminal 区间
        3. 把 base_g 限制在 fast 区间，用作前 5 年目标
        4. 中间 5 年向 stable 区间收敛
        5. terminal_g 结合参数 perpetual_growth 和 sector 的 terminal 区间
    """

    # 1) 行业识别（需要 ticker）
    sector = infer_sector_from_facts(facts, ticker)
    ranges = SECTOR_GROWTH.get(sector, SECTOR_GROWTH["CONSUMER"])
    fast_low, fast_high = ranges["fast"]
    stable_low, stable_high = ranges["stable"]
    term_low, term_high = ranges["terminal"]

    # 2) 基准增长率（分析师预测 or 历史 CAGR）
    base_g = adopt_growth_rate(ticker, revenue)  # 👈 注意这里用 ticker + revenue
    pprint(f"Base growth rate adopted: {base_g:.2%} for sector {sector}")

    # fast 阶段目标增长率：限制在 fast 范围内
    g_fast = max(min(base_g, fast_high), fast_low)
    pprint(f"Fast stage growth rate set to: {g_fast:.2%} (range {fast_low:.2%} - {fast_high:.2%})")

    # stable 阶段目标增长率：可以简单用 stable 区间的中值，
    # 也可以基于 base_g 调整，这里用中值就好
    g_stable = 0.5 * (stable_low + stable_high)
    pprint(f"Stable stage growth rate set to: {g_stable:.2%} (range {stable_low:.2%} - {stable_high:.2%})")


    # terminal growth：结合参数 perpetual_growth 和行业区间
    g_terminal_raw = perpetual_growth
    g_terminal = max(min(g_terminal_raw, term_high), term_low)

    # 3) 构造 10 年增长路径：
    #    Years 1–5: 从 g_fast 逐步过渡到 g_stable
    #    Years 6–10: 从 g_stable 逐步过渡到 g_terminal
    g1_5 = list(np.linspace(g_fast, g_stable, 5))
    g6_10 = list(np.linspace(g_stable, g_terminal, 5))

    growth_path = g1_5 + g6_10  # 共 10 个增长率
    pprint("Growth path:")
    pprint(growth_path)
    return growth_path, g_terminal

# ============================
#  两阶段增长路径：过去五年（avg. profit margin & avg. fcf profit margin ）来预测未来三年 
# ============================

# =======================================
#  主流程：构建 DCF 估值 （贴现现金流）
#  DCF（Discounted Cash Flow，贴现现金流）是一种估值方法：
# 把公司未来可获得的现金流折现到现在，把它们加总，得到公司当前的价值。
# 直观上就是“未来的钱值现在多少钱”。
# 折现未来若干年的自由现金流之和，再加上终值（terminal value）的现值：
#========================================
def build_dcf(
    ticker: str,
    required_return: float = 0.07,
    perpetual_growth: float = 0.025,
    avg_years: int = 5,
    projection_years: int = 10,   # 👈 默认做 10 年
    sector: Optional[str] = None, # 👈 新增：可手动指定 sector（TECH / CONSUMER / ...）
    save_raw_json: bool = False,
    save_raw_csv: bool = False,
):
    cik = fetch_cik(ticker)
    facts = fetch_companyfacts(cik)

    # Use extract_all_financials for full data access
    all_data = extract_all_financials(facts)

    revenue, revenue_tag, revenue_periods = all_data["revenue"]
    net_income, net_income_tag, net_income_periods = all_data["net_income"]
    _, cfo_tag, cfo_periods = all_data["cfo"]
    _, capex_tag, capex_periods = all_data["capex"]
    fcf = all_data["fcf"][0]

    # Extra series + per-year tags for 10K output
    gross_profit, gross_profit_tag, _ = all_data["gross_profit"]
    eps_diluted, eps_tag, _ = all_data["eps_diluted"]
    cash, cash_tag, _ = all_data["cash"]
    total_debt = all_data["total_debt"][0]  # derived, no single tag
    long_term_debt_tag = all_data["long_term_debt"][1]
    short_term_debt_tag = all_data["short_term_debt"][1]
    shares_tag = all_data["shares_outstanding"][1]

    # 得到net margin & FCF to margin 历史值
    net_margin, fcf_to_ni, avg_net_margin, avg_fcf_to_ni = compute_margins(
        revenue, net_income, fcf, avg_years
    )

    # 流通股数
    shares_series = all_data["shares_outstanding"][0]
    if shares_series is not None and not shares_series.empty:
        shares = float(shares_series.iloc[-1])
    else:
        shares = None

    # ---------- 历史表 ----------
    years = sorted(set(revenue.index) | set(net_income.index) | set(fcf.index))
    years = [int(y) for y in years if isinstance(y, (int, np.integer))]

    def pick(s: pd.Series, y: int):
        try:
            return float(s.loc[y])
        except Exception:
            return np.nan

    def pick_raw(s: pd.Series, y: int):
        try:
            return float(s.loc[y])
        except Exception:
            return np.nan

    # Helper: pick tag name for a given year from per-year tag dict
    def pick_tag(tag_dict, y):
        if isinstance(tag_dict, dict):
            return tag_dict.get(y, "")
        return tag_dict or ""

    # Helper: pick period (start, end) for a given year
    def pick_period(periods: dict, y: int):
        p = periods.get(y)
        if not p:
            return (None, None)
        return p

    # Gross margin helper
    def gross_margin_pct(y):
        rev = pick(revenue, y)
        gp = pick(gross_profit, y)
        if np.isfinite(rev) and np.isfinite(gp) and rev != 0:
            return gp / rev * 100
        return np.nan

    hist_df = pd.DataFrame({
        "Year": years,
        "Revenue (M)": [pick(revenue, y) / 1e6 for y in years],
        "Gross Margin (%)": [gross_margin_pct(y) for y in years],
        "Net Income (M)": [pick(net_income, y) / 1e6 for y in years],
        "Net Profit Margin (%)": [pick_raw(net_margin, y) * 100 for y in years],
        "Free Cash Flow (M)": [pick(fcf, y) / 1e6 for y in years],
        "FCF to Profit Margin (%)": [pick_raw(fcf_to_ni, y) * 100 for y in years],
        "EPS Diluted ($)": [pick(eps_diluted, y) for y in years],
        "Cash (B)": [pick(cash, y) / 1e9 for y in years],
        "Total Debt (B)": [pick(total_debt, y) / 1e9 for y in years],
        "Shares Outstanding (M)": [pick(shares_series, y) / 1e6 for y in years],
        # per-year XBRL tags — data source for each value
        "Revenue Tag": [pick_tag(revenue_tag, y) for y in years],
        "Net Income Tag": [pick_tag(net_income_tag, y) for y in years],
        "CFO Tag": [pick_tag(cfo_tag, y) for y in years],
        "CapEx Tag": [pick_tag(capex_tag, y) for y in years],
        "Gross Profit Tag": [pick_tag(gross_profit_tag, y) for y in years],
        "EPS Tag": [pick_tag(eps_tag, y) for y in years],
        "Cash Tag": [pick_tag(cash_tag, y) for y in years],
        "LT Debt Tag": [pick_tag(long_term_debt_tag, y) for y in years],
        "ST Debt Tag": [pick_tag(short_term_debt_tag, y) for y in years],
        "Shares Tag": [pick_tag(shares_tag, y) for y in years],
        "Start": [pick_period(revenue_periods, y)[0] for y in years],
        "End": [pick_period(revenue_periods, y)[1] for y in years],
    })

    # Transpose: years become columns (sorted ascending), metrics become rows
    hist_df = hist_df.set_index("Year").T
    hist_df = hist_df[sorted(hist_df.columns)]
    hist_df.index.name = None

    # ---------- 预测期（10 年） ----------
    if revenue.empty:
        raise ValueError("No revenue data available for this ticker")

    last_year = int(revenue.index.max())
    base_rev = float(revenue.loc[last_year])

    # 三阶段增长路径（10 年）+ 永续增速
    growth_path, terminal_g = build_growth_curve(
        ticker=ticker,
        facts=facts,
        revenue=revenue,
        perpetual_growth=perpetual_growth,
        avg_years=avg_years,
    )

    # 确保 projection_years 至少 10
    projection_years = max(projection_years, len(growth_path))

    proj_years = [last_year + i for i in range(1, projection_years + 1)]
    proj_rev = []
    cur_rev = base_rev
    for i in range(projection_years):
        g = growth_path[i] if i < len(growth_path) else growth_path[-1]
        cur_rev *= (1.0 + g)
        proj_rev.append(cur_rev)

    # 计算用于投影的 FCF margin（提取成独立函数以便测试/覆盖）
    fcf_margin = compute_fcf_margin(revenue, fcf, avg_net_margin, avg_fcf_to_ni, avg_years)
    proj_fcf = [r * fcf_margin for r in proj_rev]





    # 折现 + 终值（在第 projection_years 年之后）
    dfs = [(1.0 + required_return) ** i for i in range(1, projection_years + 1)]
    pv_fcfs = [proj_fcf[i] / dfs[i] for i in range(projection_years)]

    terminal_fcf = proj_fcf[-1] * (1.0 + terminal_g)
    terminal_value = terminal_fcf / (required_return - terminal_g)
    pv_terminal = terminal_value / ((1.0 + required_return) ** projection_years)

    todays_value = sum(pv_fcfs) + pv_terminal
    fair_value = todays_value / shares if (shares is not None and shares > 0) else np.nan

    # ---------- 预测表 ----------
    # For projections, use the tag from the most recent year as the reference
    latest_rev_tag = pick_tag(revenue_tag, last_year)
    latest_cfo_tag = pick_tag(cfo_tag, last_year)
    latest_capex_tag = pick_tag(capex_tag, last_year)
    base_period = revenue_periods.get(last_year, (None, None))

    proj_df = pd.DataFrame({
        "Year": proj_years,
        "Revenue (M)": [x / 1e6 for x in proj_rev],
        "Free Cash Flow (M)": [x / 1e6 for x in proj_fcf],
        "Growth Rate (%)": [g * 100 for g in growth_path[:projection_years]],
        "Discount Factor": [round(x, 2) for x in dfs],
        "PV of Future Cash Flow (M)": [x / 1e6 for x in pv_fcfs],
        "Revenue Tag": [latest_rev_tag] * len(proj_years),
        "CFO Tag": [latest_cfo_tag] * len(proj_years),
        "CapEx Tag": [latest_capex_tag] * len(proj_years),
        "Base Start": [base_period[0]] * len(proj_years),
        "Base End": [base_period[1]] * len(proj_years),
    })

    # ---------- 汇总元数据 ----------
    units = facts.get("facts", {}).get("us-gaap", {}).get("Revenues", {}).get("units", {})
    currency = next(iter(units.keys()), "N/A")

    # prefer caller-provided sector (manual override) else infer from facts
    meta = {
        "Avg Net Profit Margin (%)": avg_net_margin * 100 if not math.isnan(avg_net_margin) else np.nan,
        "Avg FCF/Net Income (%)": avg_fcf_to_ni * 100 if not math.isnan(avg_fcf_to_ni) else np.nan,
        "Sector": sector if sector is not None else infer_sector_from_facts(facts, ticker),
        "Growth Model": "3-Stage 10-Year",
        # tags used to produce the core series
        "Revenue Tag": latest_rev_tag,
        "Net Income Tag": pick_tag(net_income_tag, last_year),
        "CFO Tag": latest_cfo_tag,
        "CapEx Tag": latest_capex_tag,
        "Adopted Growth Rate Year1 (%)": growth_path[0] * 100,
        "Adopted Growth Rate Year10 (%)": growth_path[-1] * 100,
        "Terminal Growth (%)": terminal_g * 100,
        "Required Return (%)": required_return * 100,
        "PV Terminal (M)": pv_terminal / 1e6,
        "Enterprise Value (M)": todays_value / 1e6,
        "Shares Outstanding (M)": shares / 1e6 if shares else np.nan,
        "Fair Value / Share ": fair_value,
        "Currency": currency,
    }

    # Transpose: years become columns, metrics become rows
    proj_df = proj_df.set_index("Year").T
    proj_df.index.name = None

    return hist_df, proj_df, meta

#python dcf_builder.py --ticker GOOGL --required 0.07 --perp 0.025 --avg-years 5
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--required", type=float, default=0.07)
    ap.add_argument("--perp", type=float, default=0.025)
    ap.add_argument("--years", type=int, default=4)
    ap.add_argument("--avg-years", type=int, default=5)
    ap.add_argument("--no-raw-json", action="store_true", help="不保存原始 JSON")
    ap.add_argument("--no-raw-csv", action="store_true", help="不保存原始 CSV")
    ap.add_argument("--sector", type=str, default=None,
                help="手动指定行业 (TECH / CONSUMER / BANK / INSURANCE / ENERGY / PHARMA)。若不指定则自动根据 SIC 判定")
    args = ap.parse_args()

    ticker_upper = args.ticker.upper()
    currYear = pd.Timestamp.now().year
    base = f"{currYear}_dcf_{ticker_upper}"
    # --- Sector inference ---
    if args.sector:  
        # 用户手动指定
        sector = args.sector.upper()
        sector_source = "manual"
    else:
        # 自动从 SEC facts 推断
        cik = fetch_cik(args.ticker)
        facts = fetch_companyfacts(cik)
        sector = infer_sector_from_facts(facts, args.ticker)
        sector_source = "sic"

    print(f"[INFO] Sector = {sector} (source: {sector_source})")

    # --- main DCF flow ---
    hist, proj, meta = build_dcf(
        ticker=args.ticker,
        required_return=args.required,
        perpetual_growth=args.perp,
        avg_years=args.avg_years,
        projection_years=args.years,
        sector=sector,
    )

    # Save DCF outputs (你的原代码)
    hist.to_csv(base + ".csv", index=True)
    proj.to_csv(base + "_proj.csv", index=True)
    with open(base + "_meta.json", "w") as f:
        json.dump({
            k: (f"{v:,.2f}" if isinstance(v, (int, float)) else v)
            for k, v in meta.items()
        }, f, indent=2)

    # --- Save raw companyfacts JSON ---
    if not args.no_raw_json:
        cik = fetch_cik(args.ticker)
        facts = fetch_companyfacts(cik)

        fname_json = base + "_raw.json"
        with open(fname_json, "w") as f:
            json.dump(facts, f, indent=2)
        # print(f"[Saved] {fname_json}")

    # --- Save raw CSV ---
    if not args.no_raw_csv:
        cik = fetch_cik(args.ticker)
        facts = fetch_companyfacts(cik)

        raw_df = companyfacts_to_table(facts)
        fname_csv = base + "_raw.csv"
        raw_df.to_csv(fname_csv, index=False)
        print(f"[Saved] {fname_csv}")

    print(f"\nAll done. Files saved with base name: {base}\n")

# ============================
#  Test / command line entry point
# ============================

# Entry 1: Uncomment below to enable command line execution
# if __name__ == "__main__":
#     main()

# ============================
#  Test / direct function call entry point
# ============================

# Entry 2: 直接在代码里调用，不用命令行参数
import json
import pandas as pd
#   直接调用的入口函数
def run_dcf_once(
    ticker: str = "GOOGL",
    required_return: float = 0.07,
    perpetual_growth: float = 0.025,
    projection_years: int = 4,
    avg_years: int = 5,
    save_raw_json: bool = False,
    save_raw_csv: bool = False,
    sector: Optional[str] = None,
    sector_source: Optional[str] = None,
):
    """
    直接在代码里调用的入口，不再用命令行参数。
    """
    ticker_upper = ticker.upper()
    curr_year = pd.Timestamp.now().year
    base = f"{curr_year}_dcf_{ticker_upper}"
    
    # --- main DCF flow ---
    hist, proj, meta = build_dcf(
        ticker=ticker,
        required_return=required_return,
        perpetual_growth=perpetual_growth,
        avg_years=avg_years,
        projection_years=projection_years,
        sector=sector,
    )

    # 保存 DCF 结果
    hist.to_csv(base + "_10K.csv", index=True)
    proj.to_csv(base + "_proj.csv", index=True)
    with open(base + "_meta.json", "w") as f:
        json.dump(
            {
                k: (f"{v:,.2f}" if isinstance(v, (int, float)) else v)
                for k, v in meta.items()
            },
            f,
            indent=2,
        )

    # --- 保存原始 companyfacts JSON ---
    if save_raw_json:
        cik = fetch_cik(ticker)
        facts = fetch_companyfacts(cik)
        fname_json = base + "_raw.json"
        with open(fname_json, "w") as f:
            json.dump(facts, f, indent=2)
        print(f"[Saved] {fname_json}")

    # --- 保存原始 CSV ---
    if save_raw_csv:
        cik = fetch_cik(ticker)
        facts = fetch_companyfacts(cik)
        raw_df = companyfacts_to_table(facts)
        fname_csv = base + "_raw.csv"
        raw_df.to_csv(fname_csv, index=False)
        print(f"[Saved] {fname_csv}")

    print(f"\nAll done. Files saved with base name: {base}\n")
    return hist, proj, meta

# CLI entry point: supports --ticker, --required, --perp, etc.
if __name__ == "__main__":
    main()