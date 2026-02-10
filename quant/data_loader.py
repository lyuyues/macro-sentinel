"""Load and cache historical price and macro data."""
import os
import glob
import json
import pandas as pd
import numpy as np
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")


def load_price_data(
    tickers: list,
    start: str = "2016-01-01",
    end: str = "2026-02-01",
    use_cache: bool = True,
) -> pd.DataFrame:
    """Load daily adjusted close prices for a list of tickers via yfinance.

    Returns a DataFrame with DatetimeIndex and one column per ticker.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = "prices_{}_{}_{}.csv".format(
        "_".join(sorted(tickers)), start, end
    )
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if use_cache and os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        return df

    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    if data.empty:
        return pd.DataFrame()

    # Handle both single and multi-ticker column formats
    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        # Single ticker: columns are just ['Close', 'High', ...]
        prices = data[["Close"]].rename(columns={"Close": tickers[0]})

    prices.index = pd.to_datetime(prices.index)
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)

    if use_cache:
        prices.to_csv(cache_path)

    return prices


def load_vix(start: str = "2016-01-01", end: str = "2026-02-01") -> pd.Series:
    """Load daily VIX closing values."""
    df = load_price_data(["^VIX"], start=start, end=end, use_cache=True)
    if df.empty:
        return pd.Series(dtype=float, name="VIX")
    col = df.columns[0]
    return df[col].rename("VIX")


def load_yield_spread(start: str = "2016-01-01", end: str = "2026-02-01") -> pd.Series:
    """Load 10Y-2Y Treasury yield spread from FRED (CSV endpoint).

    Returns a Series indexed by date with the spread in percentage points.
    Falls back to NaN if unavailable.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, "t10y2y_{}_{}.csv".format(start, end))

    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        return df.squeeze()

    url = (
        "https://fred.stlouisfed.org/graph/fredgraph.csv"
        "?id=T10Y2Y&cosd={}&coed={}".format(start, end)
    )
    try:
        df = pd.read_csv(url, parse_dates=["DATE"], index_col="DATE")
        s = df["T10Y2Y"].replace(".", np.nan).astype(float)
        s.name = "T10Y2Y"
        s.to_frame().to_csv(cache_path)
        return s
    except Exception:
        return pd.Series(dtype=float, name="T10Y2Y")


def load_fundamental_data(ticker: str, output_dir: str = "output") -> dict:
    """Load pre-computed DCF and market data from output/<TICKER>/ directory.

    Returns dict with keys: 'hist_df', 'meta', 'market_df' (all as DataFrames/dicts).
    """
    ticker = ticker.upper()
    base = os.path.join(output_dir, ticker)
    result = {}

    hist_files = sorted(glob.glob(os.path.join(base, "*_dcf_*_10K.csv")))
    if hist_files:
        result["hist_df"] = pd.read_csv(hist_files[-1], index_col=0)

    meta_files = sorted(glob.glob(os.path.join(base, "*_meta.json")))
    if meta_files:
        with open(meta_files[-1]) as f:
            result["meta"] = json.load(f)

    market_files = sorted(glob.glob(os.path.join(base, "*_market_*.csv")))
    if market_files:
        result["market_df"] = pd.read_csv(market_files[-1], index_col=0)

    return result


def get_monthly_rebalance_dates(date_index: pd.DatetimeIndex) -> list:
    """Get the first trading day of each month from a DatetimeIndex."""
    monthly = date_index.to_series().groupby(
        [date_index.year, date_index.month]
    ).first()
    return [pd.Timestamp(v) for v in monthly.values]
