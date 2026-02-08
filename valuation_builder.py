#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
valuation_builder.py — Comprehensive valuation template builder

Pulls ~30 financial fields from SEC EDGAR (via dcf_builder) plus historical
prices from yfinance, then assembles:
  - Income statement section
  - Balance sheet items
  - Cash flow section
  - Valuation ratios (P/E, P/S, P/B, EV/Revenue, EV/EBITDA, ROE, ROA, ROIC)
  - DCF projection (reuses build_dcf logic)

Usage:
    python valuation_builder.py --ticker AMD
    python valuation_builder.py --ticker AAPL --output valuation_AAPL.csv
"""

import argparse
import json
import math
import sys

import numpy as np
import pandas as pd

from dcf_builder import (
    fetch_company_data,
    extract_all_financials,
    build_dcf,
)
from dcf_utils import (
    get_historical_year_end_prices,
    compute_wacc,
    infer_sector_from_facts,
)


# =======================================
#  Core builder
# =======================================

def build_valuation(
    ticker: str,
    required_return: float = 0.07,
    perpetual_growth: float = 0.025,
    avg_years: int = 5,
    projection_years: int = 10,
) -> dict:
    """Build comprehensive valuation template.

    Returns dict with keys:
      - "header": dict of metadata (ticker, company name, sector, etc.)
      - "income_statement": DataFrame (Revenue, Gross Profit, Op Income, NI, EPS, etc.)
      - "balance_sheet": DataFrame (Cash, Debt, Assets, Equity)
      - "cash_flow": DataFrame (CFO, CapEx, FCF)
      - "valuation_ratios": DataFrame (Market Cap, EV, P/E, P/S, P/B, etc.)
      - "dcf": dict (projected FCF, fair value, assumptions)
    """

    # 1. Fetch data from SEC EDGAR
    print(f"[valuation] Fetching SEC data for {ticker}...")
    cik, facts = fetch_company_data(ticker)
    data = extract_all_financials(facts)

    # Helper to get series from data dict
    def s(key):
        return data[key][0]

    def tag(key):
        return data[key][1]

    # Determine year range from revenue (primary series)
    revenue = s("revenue")
    if revenue.empty:
        raise ValueError(f"No revenue data available for {ticker}")

    all_years = sorted(set(revenue.index))
    all_years = [int(y) for y in all_years if isinstance(y, (int, np.integer))]

    if not all_years:
        raise ValueError(f"No valid year data for {ticker}")

    start_year = all_years[0]
    end_year = all_years[-1]

    # 2. Get historical year-end prices from yfinance
    print(f"[valuation] Fetching historical prices for {ticker} ({start_year}-{end_year})...")
    year_end_prices = get_historical_year_end_prices(ticker, start_year, end_year)

    # Helper to safely pick a value from a series by year
    def pick(series, y):
        try:
            v = float(series.loc[y])
            return v if np.isfinite(v) else np.nan
        except Exception:
            return np.nan

    # 3. Build Income Statement section
    print("[valuation] Building income statement...")
    income_rows = []
    for y in all_years:
        rev = pick(s("revenue"), y)
        gp = pick(s("gross_profit"), y)
        oi = pick(s("operating_income"), y)
        ni = pick(s("net_income"), y)
        ebitda = pick(s("ebitda"), y)
        da = pick(s("da"), y)
        interest = pick(s("interest_expense"), y)
        tax = pick(s("income_tax"), y)
        pretax = pick(s("income_before_tax"), y)
        eps = pick(s("eps_diluted"), y)
        dps = pick(s("dividends_per_share"), y)

        # Derived margins
        gross_margin = (gp / rev * 100) if (rev and np.isfinite(gp) and rev != 0) else np.nan
        op_margin = (oi / rev * 100) if (rev and np.isfinite(oi) and rev != 0) else np.nan
        net_margin = (ni / rev * 100) if (rev and np.isfinite(ni) and rev != 0) else np.nan

        income_rows.append({
            "Year": y,
            "Revenue (M)": rev / 1e6 if np.isfinite(rev) else np.nan,
            "Gross Profit (M)": gp / 1e6 if np.isfinite(gp) else np.nan,
            "Gross Margin (%)": gross_margin,
            "Operating Income (M)": oi / 1e6 if np.isfinite(oi) else np.nan,
            "Operating Margin (%)": op_margin,
            "EBITDA (M)": ebitda / 1e6 if np.isfinite(ebitda) else np.nan,
            "D&A (M)": da / 1e6 if np.isfinite(da) else np.nan,
            "Interest Expense (M)": interest / 1e6 if np.isfinite(interest) else np.nan,
            "Income Before Tax (M)": pretax / 1e6 if np.isfinite(pretax) else np.nan,
            "Income Tax (M)": tax / 1e6 if np.isfinite(tax) else np.nan,
            "Net Income (M)": ni / 1e6 if np.isfinite(ni) else np.nan,
            "Net Margin (%)": net_margin,
            "EPS (Diluted)": eps,
            "Dividends Per Share": dps,
        })
    income_df = pd.DataFrame(income_rows)

    # 4. Build Balance Sheet section
    print("[valuation] Building balance sheet...")
    bs_rows = []
    for y in all_years:
        cash = pick(s("cash"), y)
        ltd = pick(s("long_term_debt"), y)
        std = pick(s("short_term_debt"), y)
        td = pick(s("total_debt"), y)
        assets = pick(s("total_assets"), y)
        equity = pick(s("stockholders_equity"), y)
        shares = pick(s("shares_outstanding"), y)

        bs_rows.append({
            "Year": y,
            "Cash & Equivalents (M)": cash / 1e6 if np.isfinite(cash) else np.nan,
            "Short-Term Debt (M)": std / 1e6 if np.isfinite(std) else np.nan,
            "Long-Term Debt (M)": ltd / 1e6 if np.isfinite(ltd) else np.nan,
            "Total Debt (M)": td / 1e6 if np.isfinite(td) else np.nan,
            "Total Assets (M)": assets / 1e6 if np.isfinite(assets) else np.nan,
            "Stockholders' Equity (M)": equity / 1e6 if np.isfinite(equity) else np.nan,
            "Shares Outstanding (M)": shares / 1e6 if np.isfinite(shares) else np.nan,
        })
    balance_sheet_df = pd.DataFrame(bs_rows)

    # 5. Build Cash Flow section
    print("[valuation] Building cash flow...")
    cf_rows = []
    for y in all_years:
        cfo = pick(s("cfo"), y)
        capex = pick(s("capex"), y)
        fcf = pick(s("fcf"), y)

        fcf_margin = (fcf / pick(s("revenue"), y) * 100) if (np.isfinite(fcf) and pick(s("revenue"), y) != 0) else np.nan

        cf_rows.append({
            "Year": y,
            "Cash from Operations (M)": cfo / 1e6 if np.isfinite(cfo) else np.nan,
            "Capital Expenditures (M)": capex / 1e6 if np.isfinite(capex) else np.nan,
            "Free Cash Flow (M)": fcf / 1e6 if np.isfinite(fcf) else np.nan,
            "FCF Margin (%)": fcf_margin,
        })
    cash_flow_df = pd.DataFrame(cf_rows)

    # 6. Build Valuation Ratios section
    print("[valuation] Calculating valuation ratios...")
    ratio_rows = []
    for y in all_years:
        price = pick(year_end_prices, y)
        shares = pick(s("shares_outstanding"), y)
        rev = pick(s("revenue"), y)
        ni = pick(s("net_income"), y)
        equity = pick(s("stockholders_equity"), y)
        assets = pick(s("total_assets"), y)
        td = pick(s("total_debt"), y)
        cash = pick(s("cash"), y)
        ebitda = pick(s("ebitda"), y)
        eps = pick(s("eps_diluted"), y)
        oi = pick(s("operating_income"), y)
        tax = pick(s("income_tax"), y)
        pretax = pick(s("income_before_tax"), y)

        # Market Cap & EV
        mkt_cap = price * shares if (np.isfinite(price) and np.isfinite(shares)) else np.nan
        ev = np.nan
        if np.isfinite(mkt_cap):
            debt_val = td if np.isfinite(td) else 0
            cash_val = cash if np.isfinite(cash) else 0
            ev = mkt_cap + debt_val - cash_val

        # Price ratios
        pe = price / eps if (np.isfinite(price) and np.isfinite(eps) and eps != 0) else np.nan
        ps = mkt_cap / rev if (np.isfinite(mkt_cap) and np.isfinite(rev) and rev != 0) else np.nan
        pb = mkt_cap / equity if (np.isfinite(mkt_cap) and np.isfinite(equity) and equity != 0) else np.nan
        ev_rev = ev / rev if (np.isfinite(ev) and np.isfinite(rev) and rev != 0) else np.nan
        ev_ebitda = ev / ebitda if (np.isfinite(ev) and np.isfinite(ebitda) and ebitda != 0) else np.nan

        # Profitability ratios
        roe = (ni / equity * 100) if (np.isfinite(ni) and np.isfinite(equity) and equity != 0) else np.nan
        roa = (ni / assets * 100) if (np.isfinite(ni) and np.isfinite(assets) and assets != 0) else np.nan

        # ROIC = NOPAT / Invested Capital
        # NOPAT = Operating Income * (1 - tax_rate)
        # Invested Capital = Total Debt + Equity
        tax_rate = (tax / pretax) if (np.isfinite(tax) and np.isfinite(pretax) and pretax != 0) else np.nan
        nopat = oi * (1 - tax_rate) if (np.isfinite(oi) and np.isfinite(tax_rate)) else np.nan
        invested_cap = np.nan
        if np.isfinite(equity):
            debt_val = td if np.isfinite(td) else 0
            invested_cap = debt_val + equity
        roic = (nopat / invested_cap * 100) if (np.isfinite(nopat) and np.isfinite(invested_cap) and invested_cap != 0) else np.nan

        ratio_rows.append({
            "Year": y,
            "Year-End Price": price,
            "Market Cap (M)": mkt_cap / 1e6 if np.isfinite(mkt_cap) else np.nan,
            "Enterprise Value (M)": ev / 1e6 if np.isfinite(ev) else np.nan,
            "P/E": pe,
            "P/S": ps,
            "P/B": pb,
            "EV/Revenue": ev_rev,
            "EV/EBITDA": ev_ebitda,
            "ROE (%)": roe,
            "ROA (%)": roa,
            "ROIC (%)": roic,
            "Effective Tax Rate (%)": tax_rate * 100 if np.isfinite(tax_rate) else np.nan,
        })
    ratios_df = pd.DataFrame(ratio_rows)

    # 7. WACC (latest year only)
    print("[valuation] Computing WACC...")
    latest_year = all_years[-1]
    lt_equity = pick(s("stockholders_equity"), latest_year)
    lt_debt = pick(s("total_debt"), latest_year)
    lt_interest = pick(s("interest_expense"), latest_year)
    lt_tax = pick(s("income_tax"), latest_year)
    lt_pretax = pick(s("income_before_tax"), latest_year)
    lt_tax_rate = (lt_tax / lt_pretax) if (np.isfinite(lt_tax) and np.isfinite(lt_pretax) and lt_pretax != 0) else 0.21

    wacc = np.nan
    if np.isfinite(lt_equity) and np.isfinite(lt_debt):
        try:
            wacc = compute_wacc(
                ticker=ticker,
                total_debt=lt_debt if np.isfinite(lt_debt) else 0,
                stockholders_equity=lt_equity,
                interest_expense=lt_interest if np.isfinite(lt_interest) else 0,
                tax_rate=lt_tax_rate,
            )
        except Exception as e:
            print(f"[valuation] WACC calculation failed: {e}")

    # 8. Run DCF (reuse existing build_dcf)
    print("[valuation] Running DCF projection...")
    sector = infer_sector_from_facts(facts, ticker)
    try:
        hist_dcf, proj_dcf, dcf_meta = build_dcf(
            ticker=ticker,
            required_return=required_return,
            perpetual_growth=perpetual_growth,
            avg_years=avg_years,
            projection_years=projection_years,
            sector=sector,
        )
    except Exception as e:
        print(f"[valuation] DCF failed: {e}")
        hist_dcf = pd.DataFrame()
        proj_dcf = pd.DataFrame()
        dcf_meta = {"error": str(e)}

    # 9. Compile header
    company_name = facts.get("entityName", ticker)
    header = {
        "Ticker": ticker.upper(),
        "Company Name": company_name,
        "CIK": cik,
        "Sector": sector,
        "Data Years": f"{start_year}-{end_year}",
        "WACC (%)": wacc * 100 if np.isfinite(wacc) else np.nan,
        "Required Return (%)": required_return * 100,
        "Perpetual Growth (%)": perpetual_growth * 100,
    }
    # Merge in DCF meta
    if isinstance(dcf_meta, dict):
        header["Fair Value / Share"] = dcf_meta.get("Fair Value / Share ", np.nan)
        header["Enterprise Value (M)"] = dcf_meta.get("Enterprise Value (M)", np.nan)

    # Record which XBRL tags were used
    tag_info = {}
    for key in data:
        t = data[key][1]
        if t:
            tag_info[key] = t
    header["XBRL Tags Used"] = tag_info

    print(f"[valuation] Done. {len(all_years)} years of data assembled.")

    return {
        "header": header,
        "income_statement": income_df,
        "balance_sheet": balance_sheet_df,
        "cash_flow": cash_flow_df,
        "valuation_ratios": ratios_df,
        "dcf": {
            "historical": hist_dcf,
            "projection": proj_dcf,
            "meta": dcf_meta,
        },
    }


# =======================================
#  Output
# =======================================

def save_valuation_template(result: dict, output_path: str):
    """Save valuation to a single CSV file with sections separated by headers."""
    sections = []

    # Header section
    header = result["header"]
    header_rows = []
    for k, v in header.items():
        if k == "XBRL Tags Used":
            continue  # skip nested dict in CSV
        header_rows.append({"Field": k, "Value": v})
    header_df = pd.DataFrame(header_rows)

    sections.append(("=== COMPANY INFO ===", header_df))
    sections.append(("=== INCOME STATEMENT (M = Millions) ===", result["income_statement"]))
    sections.append(("=== BALANCE SHEET (M = Millions) ===", result["balance_sheet"]))
    sections.append(("=== CASH FLOW (M = Millions) ===", result["cash_flow"]))
    sections.append(("=== VALUATION RATIOS ===", result["valuation_ratios"]))

    dcf = result.get("dcf", {})
    if isinstance(dcf.get("projection"), pd.DataFrame) and not dcf["projection"].empty:
        sections.append(("=== DCF PROJECTION ===", dcf["projection"]))

    with open(output_path, "w") as f:
        for title, df in sections:
            f.write(f"\n{title}\n")
            df.to_csv(f, index=False)
            f.write("\n")

    print(f"[valuation] Saved to {output_path}")


def save_valuation_excel(result: dict, output_path: str):
    """Save valuation to an Excel file with separate sheets per section."""
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Header as a simple 2-column sheet
        header = result["header"]
        header_rows = []
        for k, v in header.items():
            if k == "XBRL Tags Used":
                # Flatten tag info
                for tk, tv in v.items():
                    header_rows.append({"Field": f"Tag: {tk}", "Value": tv})
            else:
                header_rows.append({"Field": k, "Value": v})
        pd.DataFrame(header_rows).to_excel(writer, sheet_name="Summary", index=False)

        result["income_statement"].to_excel(writer, sheet_name="Income Statement", index=False)
        result["balance_sheet"].to_excel(writer, sheet_name="Balance Sheet", index=False)
        result["cash_flow"].to_excel(writer, sheet_name="Cash Flow", index=False)
        result["valuation_ratios"].to_excel(writer, sheet_name="Valuation Ratios", index=False)

        dcf = result.get("dcf", {})
        if isinstance(dcf.get("projection"), pd.DataFrame) and not dcf["projection"].empty:
            dcf["projection"].to_excel(writer, sheet_name="DCF Projection", index=False)
        if isinstance(dcf.get("historical"), pd.DataFrame) and not dcf["historical"].empty:
            dcf["historical"].to_excel(writer, sheet_name="DCF Historical", index=False)

        # DCF Meta as a sheet
        if isinstance(dcf.get("meta"), dict):
            meta_rows = [{"Field": k, "Value": v} for k, v in dcf["meta"].items()]
            pd.DataFrame(meta_rows).to_excel(writer, sheet_name="DCF Assumptions", index=False)

    print(f"[valuation] Saved to {output_path}")


# =======================================
#  CLI entry point
# =======================================

def main():
    ap = argparse.ArgumentParser(description="Build comprehensive valuation template")
    ap.add_argument("--ticker", required=True, help="Stock ticker (e.g. AMD, AAPL)")
    ap.add_argument("--required", type=float, default=0.07, help="Required return rate (default 0.07)")
    ap.add_argument("--perp", type=float, default=0.025, help="Perpetual growth rate (default 0.025)")
    ap.add_argument("--avg-years", type=int, default=5, help="Years for averaging margins")
    ap.add_argument("--projection-years", type=int, default=10, help="DCF projection years")
    ap.add_argument("--output", type=str, default=None, help="Output file path (default: valuation_<TICKER>.csv)")
    ap.add_argument("--excel", action="store_true", help="Also save as Excel (.xlsx)")
    args = ap.parse_args()

    ticker = args.ticker.upper()

    result = build_valuation(
        ticker=ticker,
        required_return=args.required,
        perpetual_growth=args.perp,
        avg_years=args.avg_years,
        projection_years=args.projection_years,
    )

    # Print summary to console
    header = result["header"]
    print(f"\n{'='*50}")
    print(f"  {header['Company Name']} ({header['Ticker']})")
    print(f"  Sector: {header['Sector']}")
    print(f"  Data: {header['Data Years']}")
    fair_val = header.get('Fair Value / Share')
    if fair_val is not None and np.isfinite(fair_val):
        print(f"  DCF Fair Value / Share: ${fair_val:,.2f}")
    wacc_pct = header.get('WACC (%)')
    if wacc_pct is not None and np.isfinite(wacc_pct):
        print(f"  WACC: {wacc_pct:.2f}%")
    print(f"{'='*50}\n")

    # Save outputs
    import os
    if args.output:
        base = args.output
    else:
        out_dir = os.path.join("output", ticker)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.join(out_dir, f"valuation_{ticker}.csv")
    save_valuation_template(result, base)

    if args.excel:
        xlsx_path = base.replace(".csv", ".xlsx") if base.endswith(".csv") else base + ".xlsx"
        save_valuation_excel(result, xlsx_path)

    return result


if __name__ == "__main__":
    main()
