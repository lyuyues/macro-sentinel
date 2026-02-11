"""
Seattle Real Estate Investment Analysis
=======================================
Fetches 10-year historical data for Seattle / Eastside (Bellevue) and creates
investment-insight charts.

Data sources:
  - FRED (Federal Reserve Economic Data): mortgage rates, building permits,
    income, population, house price index, rent CPI
  - Zillow Research: city-level ZHVI (home values) and ZORI (rent index)

Output: PNG charts + summary markdown in output/Seattle_RE/
"""

from __future__ import annotations

import os
import sys
from io import StringIO
from datetime import datetime
from typing import Optional, Dict

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import requests

# ── Config ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "Seattle_RE")
os.makedirs(OUTPUT_DIR, exist_ok=True)

START = "2015-01-01"
TODAY = datetime.today().strftime("%Y-%m-%d")

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})

# ── FRED helpers ──────────────────────────────────────────────────────────────

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

FRED_SERIES = {
    # Mortgage
    "mortgage_30yr":      "MORTGAGE30US",
    # Building permits – Seattle MSA (SA = seasonally adjusted)
    "permits_total":      "SEAT653BPPRIVSA",   # all structures
    "permits_1unit":      "SEAT653BP1FHSA",    # single-family
    # Income
    "median_hh_income":   "MHIWA53033A052NCEN", # King County median HH income
    "percapita_income":   "SEAT653PCPI",        # Seattle MSA per-capita
    # Population
    "population":         "STWPOP",             # Seattle MSA resident pop
    # House Price Index
    "hpi":                "ATNHPIUS42660A",     # HPI Seattle MSA (annual)
    # Rent CPI
    "rent_cpi":           "CUURA423SEHA",       # CPI rent, Seattle MSA
}


def fetch_fred(series_id: str, start: str = START) -> pd.DataFrame | None:
    """Download a FRED series as CSV (no API key needed)."""
    url = f"{FRED_CSV}?id={series_id}&cosd={start}&coed={TODAY}"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna()
    except Exception as e:
        print(f"  [WARN] Failed to fetch FRED {series_id}: {e}")
        return None


# ── Zillow helpers ────────────────────────────────────────────────────────────

ZILLOW_ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)

ZILLOW_ZORI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zori/"
    "City_zori_uc_sfrcondomfr_sm_sa_month.csv"
)


def fetch_zillow_city(url: str, cities: dict[str, str]) -> dict[str, pd.DataFrame]:
    """
    Download Zillow Research CSV, filter to *cities* {label: city_name},
    and return {label: DataFrame(date, value)}.
    """
    results = {}
    try:
        print(f"  Downloading Zillow CSV …")
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        raw = pd.read_csv(StringIO(r.text))

        # Filter to WA state
        wa = raw[raw["StateName"] == "WA"] if "StateName" in raw.columns else raw[raw["State"] == "WA"]

        for label, city in cities.items():
            row = wa[wa["RegionName"].str.lower() == city.lower()]
            if row.empty:
                print(f"  [WARN] City '{city}' not found in Zillow data")
                continue
            # Date columns are like "2015-01-31"
            date_cols = [c for c in row.columns if c[:4].isdigit()]
            vals = row[date_cols].T
            vals.columns = ["value"]
            vals.index = pd.to_datetime(vals.index)
            vals = vals[vals.index >= START]
            vals = vals.reset_index().rename(columns={"index": "date"})
            vals["value"] = pd.to_numeric(vals["value"], errors="coerce")
            results[label] = vals.dropna()
    except Exception as e:
        print(f"  [WARN] Zillow download failed: {e}")
    return results


# ── Fetch all data ────────────────────────────────────────────────────────────

def fetch_all():
    data = {}

    print("Fetching FRED data …")
    for key, sid in FRED_SERIES.items():
        print(f"  {key} ({sid})")
        data[key] = fetch_fred(sid)

    print("Fetching Zillow ZHVI (home values) …")
    zhvi = fetch_zillow_city(ZILLOW_ZHVI_URL, {
        "Seattle": "Seattle",
        "Bellevue": "Bellevue",
        "Redmond": "Redmond",
        "Kirkland": "Kirkland",
    })
    data["zhvi"] = zhvi

    print("Fetching Zillow ZORI (rent) …")
    zori = fetch_zillow_city(ZILLOW_ZORI_URL, {
        "Seattle": "Seattle",
        "Bellevue": "Bellevue",
    })
    data["zori"] = zori

    return data


# ── Chart helpers ─────────────────────────────────────────────────────────────

def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def add_recession_bands(ax):
    """Shade COVID recession."""
    ax.axvspan(pd.Timestamp("2020-02-01"), pd.Timestamp("2020-06-01"),
               color="grey", alpha=0.15, label="COVID recession")


# ── Charts ────────────────────────────────────────────────────────────────────

def chart_home_values(data):
    """Zillow ZHVI: Seattle vs Eastside cities."""
    zhvi = data.get("zhvi", {})
    if not zhvi:
        print("  [SKIP] No Zillow ZHVI data")
        return
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = {"Seattle": "#2196F3", "Bellevue": "#F44336",
              "Redmond": "#4CAF50", "Kirkland": "#FF9800"}
    for label, df in zhvi.items():
        ax.plot(df["date"], df["value"] / 1000, label=label,
                color=colors.get(label, None), linewidth=2)
    add_recession_bands(ax)
    ax.set_title("Home Values (Zillow ZHVI) – Seattle vs Eastside")
    ax.set_ylabel("Typical Home Value ($K)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}K"))
    ax.legend()
    ax.grid(alpha=0.3)
    save(fig, "01_home_values_zhvi.png")


def chart_hpi(data):
    """FRED HPI for Seattle MSA."""
    df = data.get("hpi")
    if df is None or df.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["date"], df["value"], color="#1565C0", linewidth=2)
    add_recession_bands(ax)
    ax.set_title("House Price Index – Seattle-Tacoma-Bellevue MSA (FRED)")
    ax.set_ylabel("All-Transactions HPI (Index)")
    ax.grid(alpha=0.3)
    save(fig, "02_hpi_seattle_msa.png")


def chart_mortgage(data):
    """30-year fixed mortgage rate."""
    df = data.get("mortgage_30yr")
    if df is None or df.empty:
        return
    # Resample weekly → monthly average
    df = df.set_index("date").resample("MS").mean().reset_index()
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["date"], df["value"], color="#D32F2F", linewidth=2)
    add_recession_bands(ax)
    ax.set_title("30-Year Fixed Mortgage Rate (US Average)")
    ax.set_ylabel("Rate (%)")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax.grid(alpha=0.3)
    # Annotate current
    latest = df.iloc[-1]
    ax.annotate(f'{latest["value"]:.2f}%',
                xy=(latest["date"], latest["value"]),
                fontsize=11, fontweight="bold", color="#D32F2F",
                xytext=(10, 10), textcoords="offset points")
    save(fig, "03_mortgage_rate.png")


def chart_population(data):
    """Seattle MSA population.  FRED STWPOP is in *thousands*."""
    df = data.get("population")
    if df is None or df.empty:
        return
    # FRED STWPOP unit = thousands of persons
    pop_m = df["value"] / 1e3  # convert to millions
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(df["date"].dt.year, pop_m, color="#43A047", width=0.7)
    ax.set_title("Resident Population – Seattle-Tacoma-Bellevue MSA")
    ax.set_ylabel("Population (millions)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.2f}M"))
    for yr, val in zip(df["date"].dt.year, pop_m):
        ax.text(yr, val + 0.02, f'{val:.2f}M', ha="center", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "04_population.png")


def chart_permits(data):
    """Building permits: total vs 1-unit (multi-unit = total - 1-unit)."""
    total = data.get("permits_total")
    single = data.get("permits_1unit")
    if total is None or single is None:
        print("  [SKIP] No building permits data")
        return

    # Merge on date
    merged = pd.merge(total, single, on="date", suffixes=("_total", "_1unit"))
    merged["multi"] = merged["value_total"] - merged["value_1unit"]

    # 12-month rolling sum for cleaner view
    merged = merged.set_index("date").resample("MS").mean()
    merged["total_12m"] = merged["value_total"].rolling(12).sum()
    merged["single_12m"] = merged["value_1unit"].rolling(12).sum()
    merged["multi_12m"] = merged["multi"].rolling(12).sum()
    merged = merged.dropna().reset_index()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.stackplot(merged["date"],
                 merged["single_12m"], merged["multi_12m"],
                 labels=["Single-Family (House)", "Multi-Family (Apartment 2+ units)"],
                 colors=["#66BB6A", "#42A5F5"], alpha=0.8)
    add_recession_bands(ax)
    ax.set_title("Building Permits Issued – Seattle MSA (12-Month Rolling Total)")
    ax.set_ylabel("Permits (trailing 12 months)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    save(fig, "05_building_permits.png")


def chart_income(data):
    """Median household income + per-capita income."""
    median = data.get("median_hh_income")
    percap = data.get("percapita_income")

    fig, ax1 = plt.subplots(figsize=(12, 6))

    if median is not None and not median.empty:
        ax1.bar(median["date"].dt.year - 0.2, median["value"] / 1000,
                width=0.4, color="#1976D2", label="Median HH Income (King Co.)")
        for _, row in median.iterrows():
            ax1.text(row["date"].year - 0.2, row["value"] / 1000 + 1,
                     f"${row['value']/1000:.0f}K", ha="center", fontsize=7,
                     color="#1976D2")

    if percap is not None and not percap.empty:
        ax1.bar(percap["date"].dt.year + 0.2, percap["value"] / 1000,
                width=0.4, color="#F57C00", label="Per Capita Income (Seattle MSA)")
        for _, row in percap.iterrows():
            ax1.text(row["date"].year + 0.2, row["value"] / 1000 + 1,
                     f"${row['value']/1000:.0f}K", ha="center", fontsize=7,
                     color="#F57C00")

    ax1.set_title("Income – King County / Seattle MSA")
    ax1.set_ylabel("Income ($K)")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}K"))
    ax1.legend()
    ax1.grid(axis="y", alpha=0.3)
    save(fig, "06_income.png")


def chart_rent(data):
    """Zillow ZORI rent index + FRED CPI rent."""
    fig, ax1 = plt.subplots(figsize=(12, 6))

    zori = data.get("zori", {})
    colors_zori = {"Seattle": "#2196F3", "Bellevue": "#F44336"}
    for label, df in zori.items():
        ax1.plot(df["date"], df["value"], label=f"ZORI – {label}",
                 color=colors_zori.get(label), linewidth=2)

    ax1.set_ylabel("Zillow Observed Rent Index ($)")
    ax1.set_title("Rent – Seattle vs Bellevue (Zillow ZORI) + CPI Rent Index")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    # Overlay CPI rent on secondary axis
    rent_cpi = data.get("rent_cpi")
    if rent_cpi is not None and not rent_cpi.empty:
        ax2 = ax1.twinx()
        ax2.plot(rent_cpi["date"], rent_cpi["value"],
                 color="#9E9E9E", linewidth=1.5, linestyle="--",
                 label="CPI Rent Index (Seattle MSA)")
        ax2.set_ylabel("CPI Rent Index")
        ax2.legend(loc="lower right")

    add_recession_bands(ax1)
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)
    save(fig, "07_rent.png")


def chart_affordability(data):
    """Price-to-income ratio and price-to-rent ratio."""
    zhvi_sea = data.get("zhvi", {}).get("Seattle")
    median = data.get("median_hh_income")
    zori_sea = data.get("zori", {}).get("Seattle")

    if zhvi_sea is None or median is None:
        print("  [SKIP] Not enough data for affordability chart")
        return

    # Price-to-income: annual
    zhvi_ann = zhvi_sea.set_index("date").resample("YS").last().reset_index()
    zhvi_ann["year"] = zhvi_ann["date"].dt.year
    median["year"] = median["date"].dt.year
    merged = pd.merge(zhvi_ann[["year", "value"]], median[["year", "value"]],
                      on="year", suffixes=("_price", "_income"))
    merged["price_to_income"] = merged["value_price"] / merged["value_income"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Price-to-income
    ax = axes[0]
    ax.bar(merged["year"], merged["price_to_income"], color="#7B1FA2", width=0.7)
    for _, row in merged.iterrows():
        ax.text(row["year"], row["price_to_income"] + 0.1,
                f'{row["price_to_income"]:.1f}x', ha="center", fontsize=8)
    ax.set_title("Price-to-Income Ratio (Seattle)")
    ax.set_ylabel("Home Price / Median HH Income")
    ax.grid(axis="y", alpha=0.3)

    # Price-to-rent
    ax = axes[1]
    if zori_sea is not None and not zori_sea.empty:
        zhvi_m = zhvi_sea.set_index("date").resample("MS").last()
        zori_m = zori_sea.set_index("date").resample("MS").last()
        combined = pd.merge(zhvi_m, zori_m, left_index=True, right_index=True,
                            suffixes=("_price", "_rent"))
        combined["ptr"] = combined["value_price"] / (combined["value_rent"] * 12)
        ax.plot(combined.index, combined["ptr"], color="#00897B", linewidth=2)
        ax.set_title("Price-to-Annual-Rent Ratio (Seattle)")
        ax.set_ylabel("Home Price / Annual Rent")
        ax.grid(alpha=0.3)
    else:
        ax.text(0.5, 0.5, "No ZORI rent data available", ha="center",
                va="center", transform=ax.transAxes)

    fig.suptitle("Affordability Metrics – Seattle", fontsize=14, y=1.02)
    fig.tight_layout()
    save(fig, "08_affordability.png")


def chart_dashboard(data):
    """Combined 2x3 dashboard."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("Seattle Real Estate Investment Dashboard (10-Year)", fontsize=16)

    # 1. Home values
    ax = axes[0, 0]
    zhvi = data.get("zhvi", {})
    colors = {"Seattle": "#2196F3", "Bellevue": "#F44336",
              "Redmond": "#4CAF50", "Kirkland": "#FF9800"}
    for label, df in zhvi.items():
        ax.plot(df["date"], df["value"] / 1000, label=label,
                color=colors.get(label), linewidth=1.5)
    ax.set_title("Home Values (ZHVI)")
    ax.set_ylabel("$K")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}K"))
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # 2. Mortgage rate
    ax = axes[0, 1]
    df = data.get("mortgage_30yr")
    if df is not None:
        df_m = df.set_index("date").resample("MS").mean().reset_index()
        ax.plot(df_m["date"], df_m["value"], color="#D32F2F", linewidth=1.5)
    ax.set_title("30-Yr Mortgage Rate")
    ax.set_ylabel("%")
    ax.grid(alpha=0.3)

    # 3. Population (STWPOP in thousands)
    ax = axes[0, 2]
    df = data.get("population")
    if df is not None:
        ax.bar(df["date"].dt.year, df["value"] / 1e3, color="#43A047", width=0.7)
    ax.set_title("Population (MSA)")
    ax.set_ylabel("Millions")
    ax.grid(axis="y", alpha=0.3)

    # 4. Building permits
    ax = axes[1, 0]
    total = data.get("permits_total")
    single = data.get("permits_1unit")
    if total is not None and single is not None:
        merged = pd.merge(total, single, on="date", suffixes=("_t", "_s"))
        merged["multi"] = merged["value_t"] - merged["value_s"]
        merged = merged.set_index("date").resample("MS").mean()
        merged["s12"] = merged["value_s"].rolling(12).sum()
        merged["m12"] = merged["multi"].rolling(12).sum()
        merged = merged.dropna().reset_index()
        ax.stackplot(merged["date"], merged["s12"], merged["m12"],
                     labels=["Single-Family", "Multi-Family"],
                     colors=["#66BB6A", "#42A5F5"], alpha=0.8)
        ax.legend(fontsize=7)
    ax.set_title("Building Permits (12m rolling)")
    ax.grid(alpha=0.3)

    # 5. Income
    ax = axes[1, 1]
    median = data.get("median_hh_income")
    if median is not None:
        ax.bar(median["date"].dt.year, median["value"] / 1000,
               color="#1976D2", width=0.7)
    ax.set_title("Median HH Income (King Co.)")
    ax.set_ylabel("$K")
    ax.grid(axis="y", alpha=0.3)

    # 6. Rent
    ax = axes[1, 2]
    zori = data.get("zori", {})
    for label, df in zori.items():
        ax.plot(df["date"], df["value"], label=label,
                color=colors.get(label, "#999"), linewidth=1.5)
    ax.set_title("Rent (Zillow ZORI)")
    ax.set_ylabel("$/month")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    for row_axes in axes:
        for ax in row_axes:
            ax.xaxis.set_major_locator(mdates.YearLocator(2))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.tight_layout()
    save(fig, "00_dashboard.png")


# ── Summary ───────────────────────────────────────────────────────────────────

def write_summary(data):
    lines = ["# Seattle Real Estate Investment Analysis", ""]
    lines.append(f"Generated: {TODAY}")
    lines.append("")

    # Home values summary
    zhvi = data.get("zhvi", {})
    if zhvi:
        lines.append("## Home Values (Zillow ZHVI)")
        for label, df in zhvi.items():
            latest = df.iloc[-1]
            oldest = df.iloc[0]
            change = (latest["value"] / oldest["value"] - 1) * 100
            lines.append(
                f"- **{label}**: ${latest['value']:,.0f} "
                f"(as of {latest['date'].strftime('%Y-%m')}), "
                f"{change:+.1f}% since {oldest['date'].strftime('%Y-%m')}"
            )
        lines.append("")

    # Mortgage
    df = data.get("mortgage_30yr")
    if df is not None and not df.empty:
        latest = df.iloc[-1]
        lines.append("## Mortgage Rate")
        lines.append(f"- Current 30-yr fixed: **{latest['value']:.2f}%** "
                     f"(as of {latest['date'].strftime('%Y-%m-%d')})")
        lines.append(f"- 10-yr high: {df['value'].max():.2f}%")
        lines.append(f"- 10-yr low: {df['value'].min():.2f}%")
        lines.append("")

    # Population
    df = data.get("population")
    if df is not None and not df.empty:
        latest = df.iloc[-1]
        oldest = df.iloc[0]
        change = (latest["value"] / oldest["value"] - 1) * 100
        lines.append("## Population (Seattle MSA)")
        lines.append(f"- Latest: **{latest['value']/1e3:.2f}M** ({latest['date'].year})")
        lines.append(f"- Growth since {oldest['date'].year}: {change:+.1f}%")
        lines.append("")

    # Income
    df = data.get("median_hh_income")
    if df is not None and not df.empty:
        latest = df.iloc[-1]
        oldest = df.iloc[0]
        change = (latest["value"] / oldest["value"] - 1) * 100
        lines.append("## Median Household Income (King County)")
        lines.append(f"- Latest: **${latest['value']:,.0f}** ({latest['date'].year})")
        lines.append(f"- Growth since {oldest['date'].year}: {change:+.1f}%")
        lines.append("")

    df = data.get("percapita_income")
    if df is not None and not df.empty:
        latest = df.iloc[-1]
        lines.append("## Per Capita Income (Seattle MSA)")
        lines.append(f"- Latest: **${latest['value']:,.0f}** ({latest['date'].year})")
        lines.append("")

    # Rent
    zori = data.get("zori", {})
    if zori:
        lines.append("## Rent (Zillow ZORI)")
        for label, df in zori.items():
            latest = df.iloc[-1]
            oldest = df.iloc[0]
            change = (latest["value"] / oldest["value"] - 1) * 100
            lines.append(
                f"- **{label}**: ${latest['value']:,.0f}/mo "
                f"(as of {latest['date'].strftime('%Y-%m')}), "
                f"{change:+.1f}% since {oldest['date'].strftime('%Y-%m')}"
            )
        lines.append("")

    # Affordability
    zhvi_sea = zhvi.get("Seattle")
    if zhvi_sea is not None and df is not None:
        median = data.get("median_hh_income")
        if median is not None and not median.empty:
            latest_price = zhvi_sea.iloc[-1]["value"]
            latest_income = median.iloc[-1]["value"]
            ptr = latest_price / latest_income
            lines.append("## Affordability")
            lines.append(f"- Price-to-Income ratio: **{ptr:.1f}x**")
            zori_sea = zori.get("Seattle")
            if zori_sea is not None and not zori_sea.empty:
                annual_rent = zori_sea.iloc[-1]["value"] * 12
                price_rent = latest_price / annual_rent
                cap_rate = annual_rent / latest_price * 100
                lines.append(f"- Price-to-Annual-Rent ratio: **{price_rent:.1f}x**")
                lines.append(f"- Gross rent yield: **{cap_rate:.2f}%**")
            lines.append("")

    path = os.path.join(OUTPUT_DIR, "Seattle_RE_analysis.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Saved {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    data = fetch_all()

    print("\nGenerating charts …")
    chart_home_values(data)
    chart_hpi(data)
    chart_mortgage(data)
    chart_population(data)
    chart_permits(data)
    chart_income(data)
    chart_rent(data)
    chart_affordability(data)
    chart_dashboard(data)

    print("\nWriting summary …")
    write_summary(data)

    print("\nDone! Output in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
