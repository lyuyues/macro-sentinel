"""
Residential Property Intrinsic Value Analysis
==============================================
DCF (rental income) + Replacement Cost + Cycle Analysis
for an Eastside (Bellevue) property bought March 2019.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

OUTPUT_DIR = "output/Seattle_RE"

# ── Property Details ──────────────────────────────────────────────────────────
BUY_PRICE = 1_050_000
BUY_DATE = "2019-03"
LOAN_BALANCE = 680_000       # approx remaining
CURRENT_MARKET = 1_709_000   # estimated from Zillow ZHVI +62.8%

# ── Market Assumptions ────────────────────────────────────────────────────────

# Rental income approach
CURRENT_MONTHLY_RENT = 4_200  # market rent for comparable Eastside 4BR
VACANCY_RATE = 0.05           # 5%
MGMT_FEE_PCT = 0.00          # self-managed
PROP_TAX_RATE = 0.0100        # ~1.0% King County
INSURANCE_ANNUAL = 2_400
MAINTENANCE_PCT = 0.005       # 0.5% of value/yr
CAPEX_RESERVE_PCT = 0.01      # 1% of value/yr (roof, HVAC, etc.)

# Growth & discount
SCENARIOS = {
    "Bull": {
        "rent_growth": 0.04,       # 4%/yr
        "appreciation": 0.05,      # 5%/yr
        "discount_rate": 0.07,     # 7%
        "terminal_cap": 0.045,     # 4.5%
    },
    "Base": {
        "rent_growth": 0.025,
        "appreciation": 0.01,
        "discount_rate": 0.08,
        "terminal_cap": 0.05,
    },
    "Bear": {
        "rent_growth": 0.01,
        "appreciation": -0.05,
        "discount_rate": 0.10,
        "terminal_cap": 0.06,
    },
}

HOLD_YEARS = 10  # projection horizon

# ── Replacement Cost Assumptions ──────────────────────────────────────────────
HOUSE_SQFT = 2800          # typical 4BR Eastside
LAND_VALUE = 900_000       # Eastside lot, 2026 estimate
CONSTRUCTION_COST_SQFT = 350  # Seattle Eastside, mid-to-high quality
SOFT_COSTS_PCT = 0.15      # permits, architect, engineering
DEPRECIATION_ANNUAL = 0.01 # 1% physical depreciation for ~20yr old home


def dcf_analysis(scenario_name, params):
    """Run DCF for one scenario. Returns dict of results."""
    rent = CURRENT_MONTHLY_RENT * 12
    value = CURRENT_MARKET
    discount = params["discount_rate"]

    annual_noi = []
    annual_values = []
    annual_cashflows = []

    for yr in range(1, HOLD_YEARS + 1):
        # Gross rent
        gross_rent = rent * (1 + params["rent_growth"]) ** yr
        effective_rent = gross_rent * (1 - VACANCY_RATE)

        # Operating expenses
        prop_tax = value * PROP_TAX_RATE
        insurance = INSURANCE_ANNUAL * (1.03 ** yr)  # 3%/yr inflation
        maintenance = value * MAINTENANCE_PCT
        capex = value * CAPEX_RESERVE_PCT

        total_opex = prop_tax + insurance + maintenance + capex
        noi = effective_rent - total_opex

        # Property value
        value = CURRENT_MARKET * (1 + params["appreciation"]) ** yr

        annual_noi.append(noi)
        annual_values.append(value)

    # Terminal value (year 10 sale)
    terminal_value = annual_noi[-1] / params["terminal_cap"]
    sell_costs = terminal_value * 0.068  # 5% agent + 1.78% excise
    net_terminal = terminal_value - sell_costs

    # Discount cash flows
    pv_noi = sum(noi / (1 + discount) ** yr
                 for yr, noi in enumerate(annual_noi, 1))
    pv_terminal = net_terminal / (1 + discount) ** HOLD_YEARS

    intrinsic_value = pv_noi + pv_terminal

    return {
        "scenario": scenario_name,
        "intrinsic_value": intrinsic_value,
        "pv_noi": pv_noi,
        "pv_terminal": pv_terminal,
        "year10_noi": annual_noi[-1],
        "year10_value_appr": annual_values[-1],
        "terminal_value": terminal_value,
        "cap_rate_today": (CURRENT_MONTHLY_RENT * 12 * (1 - VACANCY_RATE)
                           - CURRENT_MARKET * (PROP_TAX_RATE + MAINTENANCE_PCT + CAPEX_RESERVE_PCT)
                           - INSURANCE_ANNUAL) / CURRENT_MARKET,
        "annual_noi": annual_noi,
        "annual_values": annual_values,
        "discount_rate": discount,
        "params": params,
    }


def replacement_cost():
    """Estimate replacement cost of the property."""
    structure_cost = HOUSE_SQFT * CONSTRUCTION_COST_SQFT
    soft_costs = structure_cost * SOFT_COSTS_PCT
    total_new = LAND_VALUE + structure_cost + soft_costs
    # Depreciation for existing home (~20 years old, 1% per year)
    age_years = 20  # estimate
    depreciated_structure = (structure_cost + soft_costs) * (1 - DEPRECIATION_ANNUAL * age_years)
    replacement_depreciated = LAND_VALUE + depreciated_structure
    return {
        "land": LAND_VALUE,
        "structure_new": structure_cost,
        "soft_costs": soft_costs,
        "total_new": total_new,
        "depreciated_structure": depreciated_structure,
        "total_depreciated": replacement_depreciated,
    }


def print_results(results, repl):
    print("=" * 70)
    print("INTRINSIC VALUE ANALYSIS — Eastside Property")
    print("=" * 70)

    # Current metrics
    annual_rent = CURRENT_MONTHLY_RENT * 12
    egi = annual_rent * (1 - VACANCY_RATE)
    opex = (CURRENT_MARKET * (PROP_TAX_RATE + MAINTENANCE_PCT + CAPEX_RESERVE_PCT)
            + INSURANCE_ANNUAL)
    noi = egi - opex
    cap_rate = noi / CURRENT_MARKET
    grm = CURRENT_MARKET / annual_rent

    print(f"\nCurrent Market Price:  ${CURRENT_MARKET:>12,.0f}")
    print(f"Annual Gross Rent:    ${annual_rent:>12,.0f}  (${CURRENT_MONTHLY_RENT:,.0f}/mo)")
    print(f"Effective Gross Inc:  ${egi:>12,.0f}  (after {VACANCY_RATE*100:.0f}% vacancy)")
    print(f"Operating Expenses:   ${opex:>12,.0f}")
    print(f"Net Operating Income: ${noi:>12,.0f}")
    print(f"Cap Rate:             {cap_rate*100:>11.2f}%")
    print(f"GRM (Gross Rent Mult):{grm:>11.1f}x")
    print(f"Price/Annual Rent:    {CURRENT_MARKET/annual_rent:>11.1f}x")

    # DCF results
    print(f"\n{'─' * 70}")
    print(f"DCF VALUATION (10-year hold, rental income)")
    print(f"{'─' * 70}")
    print(f"{'Scenario':<10} {'Discount':>8} {'PV NOI':>12} {'PV Terminal':>12} "
          f"{'Intrinsic':>12} {'vs Market':>10}")
    print(f"{'─' * 70}")
    for r in results:
        vs = (r["intrinsic_value"] / CURRENT_MARKET - 1) * 100
        marker = "UNDERVAL" if vs > 0 else "OVERVAL"
        print(f"{r['scenario']:<10} {r['discount_rate']*100:>7.0f}% "
              f"${r['pv_noi']:>11,.0f} ${r['pv_terminal']:>11,.0f} "
              f"${r['intrinsic_value']:>11,.0f} {vs:>+8.0f}% {marker}")

    # Replacement cost
    print(f"\n{'─' * 70}")
    print(f"REPLACEMENT COST ANALYSIS")
    print(f"{'─' * 70}")
    print(f"  Land value (Eastside lot):     ${repl['land']:>12,.0f}")
    print(f"  Structure ({HOUSE_SQFT} sqft × ${CONSTRUCTION_COST_SQFT}): ${repl['structure_new']:>12,.0f}")
    print(f"  Soft costs ({SOFT_COSTS_PCT*100:.0f}%):              ${repl['soft_costs']:>12,.0f}")
    print(f"  Total if built new:            ${repl['total_new']:>12,.0f}")
    print(f"  Depreciated (~20yr):           ${repl['total_depreciated']:>12,.0f}")
    print(f"  Current market:                ${CURRENT_MARKET:>12,.0f}")
    vs_new = (CURRENT_MARKET / repl["total_new"] - 1) * 100
    vs_dep = (CURRENT_MARKET / repl["total_depreciated"] - 1) * 100
    print(f"  Market vs new build:           {vs_new:>+11.0f}%")
    print(f"  Market vs depreciated:         {vs_dep:>+11.0f}%")

    # Cycle analysis
    print(f"\n{'─' * 70}")
    print(f"REAL ESTATE CYCLE POSITION (2026)")
    print(f"{'─' * 70}")
    print("""
  18-Year Real Estate Cycle (Kuznets Cycle):
  ┌─────────────────────────────────────────────────────────┐
  │ Phase 1: Recovery    (2012-2016)  ← Post-GFC recovery  │
  │ Phase 2: Expansion   (2016-2020)  ← Low rates, boom    │
  │ Phase 3: Hyper-supply (2020-2023) ← COVID spike        │
  │ Phase 4: Correction   (2023-2026) ← WE ARE HERE        │
  │ Phase 5: ???          (2026-2030)  ← Depends on inputs  │
  └─────────────────────────────────────────────────────────┘

  Key Cycle Indicators:
  ┌──────────────────────────┬───────────┬────────────┐
  │ Indicator                │ Direction │ Signal     │
  ├──────────────────────────┼───────────┼────────────┤
  │ Interest rates           │ ↓ falling │ Bullish    │
  │ Building permits         │ ↓↓ crash  │ Bullish    │
  │ Population/immigration   │ ↓↓ crash  │ BEARISH    │
  │ Home prices (Eastside)   │ → flat    │ Neutral    │
  │ Rent growth              │ ↑ slow    │ Mild bull  │
  │ Inventory (months)       │ ↑ rising  │ Bearish    │
  │ Affordability            │ → stable  │ Neutral    │
  │ Construction costs       │ ↑ record  │ Bullish*   │
  │ Tech employment          │ → stable  │ Neutral    │
  └──────────────────────────┴───────────┴────────────┘
  * High replacement cost supports existing home values

  NET ASSESSMENT: Mixed signals. Supply contraction is bullish,
  but immigration collapse is a genuine new risk not seen in
  previous cycles. Base case = FLAT with HIGH UNCERTAINTY.
""")


def chart_dcf(results):
    """Visualize DCF scenarios."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("Property Intrinsic Value Analysis", fontsize=16)

    # 1. DCF valuation comparison
    ax = axes[0]
    names = [r["scenario"] for r in results]
    values = [r["intrinsic_value"] / 1e6 for r in results]
    colors = ["#4CAF50", "#2196F3", "#F44336"]
    bars = ax.bar(names, values, color=colors, width=0.6)
    ax.axhline(CURRENT_MARKET / 1e6, color="black", linestyle="--",
               linewidth=2, label=f"Market ${CURRENT_MARKET/1e6:.2f}M")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, val + 0.02,
                f"${val:.2f}M", ha="center", fontsize=11, fontweight="bold")
    ax.set_title("DCF Intrinsic Value vs Market")
    ax.set_ylabel("Value ($M)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # 2. NOI projection
    ax = axes[1]
    for r, color in zip(results, colors):
        years = range(1, HOLD_YEARS + 1)
        ax.plot(years, [n/1000 for n in r["annual_noi"]],
                label=r["scenario"], color=color, linewidth=2, marker="o", markersize=4)
    ax.set_title("Projected Net Operating Income")
    ax.set_xlabel("Year")
    ax.set_ylabel("NOI ($K)")
    ax.legend()
    ax.grid(alpha=0.3)

    # 3. Replacement cost vs market
    ax = axes[2]
    repl = replacement_cost()
    categories = ["Market\nPrice", "Build\nNew", "Depreciated\nReplacement"]
    vals = [CURRENT_MARKET/1e6, repl["total_new"]/1e6, repl["total_depreciated"]/1e6]
    bar_colors = ["#2196F3", "#FF9800", "#9E9E9E"]
    bars = ax.bar(categories, vals, color=bar_colors, width=0.6)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, val + 0.02,
                f"${val:.2f}M", ha="center", fontsize=11, fontweight="bold")

    # Stacked breakdown for "Build New"
    ax.set_title("Market vs Replacement Cost")
    ax.set_ylabel("Value ($M)")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "10_intrinsic_value.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nSaved {path}")


def main():
    results = []
    for name, params in SCENARIOS.items():
        r = dcf_analysis(name, params)
        results.append(r)

    repl = replacement_cost()
    print_results(results, repl)
    chart_dcf(results)


if __name__ == "__main__":
    main()
