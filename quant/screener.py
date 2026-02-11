"""Screener: discover and filter DCF-qualified stocks from output/ directory."""
import os
import glob
import json
import numpy as np


def discover_tickers(output_dir="output") -> list[str]:
    """Scan output/ for tickers that have a DCF meta.json file."""
    tickers = []
    if not os.path.isdir(output_dir):
        return tickers
    for entry in sorted(os.listdir(output_dir)):
        ticker_dir = os.path.join(output_dir, entry)
        if not os.path.isdir(ticker_dir):
            continue
        meta_files = glob.glob(os.path.join(ticker_dir, "*_dcf_*_meta.json"))
        if meta_files:
            tickers.append(entry)
    return tickers


def load_ticker_summary(ticker: str, output_dir="output") -> dict:
    """Load a single ticker's meta.json summary.

    Returns dict with keys: sector, fair_value, currency, has_10k, fcf_series.
    """
    ticker = ticker.upper()
    base = os.path.join(output_dir, ticker)

    summary = {
        "sector": None,
        "fair_value": np.nan,
        "currency": None,
        "has_10k": False,
        "fcf_series": [],
    }

    # Load meta.json
    meta_files = sorted(glob.glob(os.path.join(base, "*_dcf_*_meta.json")))
    if meta_files:
        with open(meta_files[-1]) as f:
            meta = json.load(f)
        summary["sector"] = meta.get("Sector")
        fv_str = meta.get("Fair Value / Share ", "")
        try:
            summary["fair_value"] = float(str(fv_str).replace(",", ""))
        except (ValueError, TypeError):
            summary["fair_value"] = np.nan
        summary["currency"] = meta.get("Currency")

    # Check for 10K historical data
    hist_files = glob.glob(os.path.join(base, "*_dcf_*_10K.csv"))
    summary["has_10k"] = len(hist_files) > 0

    return summary


def filter_universe(
    output_dir="output",
    skip_sectors=("BANK", "INSURANCE"),
    min_fair_value=1.0,
    require_usd=True,
) -> dict:
    """Filter discovered tickers into qualified and rejected sets.

    Returns: {"qualified": {ticker: fair_value}, "rejected": {ticker: reason}}
    """
    tickers = discover_tickers(output_dir)
    qualified = {}
    rejected = {}

    for ticker in tickers:
        summary = load_ticker_summary(ticker, output_dir)

        # Check sector
        if summary["sector"] in skip_sectors:
            rejected[ticker] = f"sector:{summary['sector']}"
            continue

        # Check fair value is finite and above minimum
        fv = summary["fair_value"]
        if not np.isfinite(fv):
            rejected[ticker] = "fair_value:NaN"
            continue
        if fv < min_fair_value:
            rejected[ticker] = f"fair_value:{fv:.2f}<{min_fair_value}"
            continue

        # Check currency (allow None and "N/A" as they default to USD-traded stocks)
        if require_usd and summary["currency"] not in (None, "USD", "N/A"):
            rejected[ticker] = f"currency:{summary['currency']}"
            continue

        qualified[ticker] = fv

    return {"qualified": qualified, "rejected": rejected}
