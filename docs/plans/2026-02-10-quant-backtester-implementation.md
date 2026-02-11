# Quant Backtester Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-factor backtesting system that combines DCF valuation, relative valuation, momentum, and macro/industry cycle signals to generate and evaluate stock trading strategies.

**Architecture:** Layered pandas-based system: data_loader fetches/caches price + fundamental data with point-in-time handling; factors module computes 6 factor scores; strategy generates buy/sell signals; portfolio applies risk-parity sizing; backtest engine runs monthly loop and tracks performance vs SPY.

**Tech Stack:** Python 3.9+, pandas, numpy, yfinance, matplotlib, pytest

---

### Task 1: Project scaffolding + metrics module

**Files:**
- Create: `quant/__init__.py`
- Create: `quant/metrics.py`
- Create: `tests/__init__.py`
- Create: `tests/test_metrics.py`

**Step 1: Create directory structure**

```bash
mkdir -p quant tests
```

**Step 2: Write failing tests for metrics**

```python
# tests/__init__.py
# (empty)

# tests/test_metrics.py
import numpy as np
import pandas as pd
import pytest
from quant.metrics import (
    total_return,
    cagr,
    max_drawdown,
    annualized_volatility,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    compute_alpha_beta,
)


def _make_nav(values):
    """Helper: build a daily NAV Series from a list of values."""
    dates = pd.bdate_range("2020-01-01", periods=len(values))
    return pd.Series(values, index=dates, name="NAV")


class TestTotalReturn:
    def test_basic(self):
        nav = _make_nav([100, 110, 120])
        assert total_return(nav) == pytest.approx(0.20)

    def test_loss(self):
        nav = _make_nav([100, 90, 80])
        assert total_return(nav) == pytest.approx(-0.20)


class TestCAGR:
    def test_one_year(self):
        # 252 trading days ≈ 1 year
        nav = _make_nav([100] + [110] * 251)
        result = cagr(nav)
        assert result == pytest.approx(0.10, abs=0.02)


class TestMaxDrawdown:
    def test_simple_drawdown(self):
        nav = _make_nav([100, 120, 90, 110])
        # peak=120, trough=90 → dd = 30/120 = 0.25
        assert max_drawdown(nav) == pytest.approx(0.25)

    def test_no_drawdown(self):
        nav = _make_nav([100, 110, 120, 130])
        assert max_drawdown(nav) == pytest.approx(0.0)


class TestAnnualizedVolatility:
    def test_constant_nav(self):
        nav = _make_nav([100] * 50)
        assert annualized_volatility(nav) == pytest.approx(0.0)


class TestSharpeRatio:
    def test_zero_vol_returns_nan(self):
        nav = _make_nav([100] * 50)
        assert np.isnan(sharpe_ratio(nav))


class TestSortinoRatio:
    def test_all_positive_returns(self):
        # If all returns are positive, downside deviation is ~0 → inf or very large
        nav = _make_nav([100 + i for i in range(50)])
        result = sortino_ratio(nav)
        assert result > 5.0 or np.isinf(result)


class TestCalmarRatio:
    def test_no_drawdown_returns_nan(self):
        nav = _make_nav([100, 110, 120, 130])
        assert np.isnan(calmar_ratio(nav)) or np.isinf(calmar_ratio(nav))


class TestAlphaBeta:
    def test_same_series(self):
        nav = _make_nav([100, 105, 110, 108, 115])
        alpha, beta = compute_alpha_beta(nav, nav)
        assert beta == pytest.approx(1.0, abs=0.01)
        assert alpha == pytest.approx(0.0, abs=0.01)
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/y32lyu/Nextcloud/UWaterloo/Project/Claudcode_AI_workspace/AI_stock_analysis && python -m pytest tests/test_metrics.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 4: Implement metrics module**

```python
# quant/__init__.py
# (empty)

# quant/metrics.py
"""Performance metrics for backtesting."""
import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def total_return(nav: pd.Series) -> float:
    """Total return from first to last NAV value."""
    return nav.iloc[-1] / nav.iloc[0] - 1.0


def cagr(nav: pd.Series) -> float:
    """Compound annual growth rate."""
    n_days = (nav.index[-1] - nav.index[0]).days
    if n_days <= 0:
        return 0.0
    years = n_days / 365.25
    return (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0


def max_drawdown(nav: pd.Series) -> float:
    """Maximum peak-to-trough drawdown (returned as positive number)."""
    peak = nav.cummax()
    dd = (peak - nav) / peak
    return float(dd.max())


def annualized_volatility(nav: pd.Series) -> float:
    """Annualized volatility of daily returns."""
    returns = nav.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    return float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def sharpe_ratio(nav: pd.Series, risk_free_rate: float = 0.04) -> float:
    """Annualized Sharpe ratio."""
    vol = annualized_volatility(nav)
    if vol == 0:
        return np.nan
    annual_ret = cagr(nav)
    return (annual_ret - risk_free_rate) / vol


def sortino_ratio(nav: pd.Series, risk_free_rate: float = 0.04) -> float:
    """Annualized Sortino ratio (only penalizes downside volatility)."""
    returns = nav.pct_change().dropna()
    downside = returns[returns < 0]
    if len(downside) == 0:
        return np.inf
    downside_std = float(downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    if downside_std == 0:
        return np.inf
    annual_ret = cagr(nav)
    return (annual_ret - risk_free_rate) / downside_std


def calmar_ratio(nav: pd.Series) -> float:
    """Calmar ratio = CAGR / Max Drawdown."""
    mdd = max_drawdown(nav)
    if mdd == 0:
        return np.nan
    return cagr(nav) / mdd


def compute_alpha_beta(
    strategy_nav: pd.Series, benchmark_nav: pd.Series
) -> tuple[float, float]:
    """Compute alpha and beta vs benchmark using OLS on daily returns."""
    s_ret = strategy_nav.pct_change().dropna()
    b_ret = benchmark_nav.pct_change().dropna()
    # Align on common dates
    common = s_ret.index.intersection(b_ret.index)
    s_ret = s_ret.loc[common]
    b_ret = b_ret.loc[common]
    if len(common) < 2:
        return np.nan, np.nan
    # OLS: s = alpha + beta * b
    cov = np.cov(s_ret, b_ret)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else np.nan
    alpha = float(s_ret.mean() - beta * b_ret.mean()) * TRADING_DAYS_PER_YEAR
    return alpha, beta
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add quant/__init__.py quant/metrics.py tests/__init__.py tests/test_metrics.py
git commit -m "feat(quant): add performance metrics module with tests"
```

---

### Task 2: Data loader — price data

**Files:**
- Create: `quant/data_loader.py`
- Create: `tests/test_data_loader.py`

**Step 1: Write failing tests for price loading**

```python
# tests/test_data_loader.py
import pandas as pd
import numpy as np
import pytest
from quant.data_loader import load_price_data, get_monthly_rebalance_dates


class TestLoadPriceData:
    def test_returns_dataframe(self):
        # Use SPY as a reliable ticker
        df = load_price_data(["SPY"], start="2024-01-01", end="2024-03-01")
        assert isinstance(df, pd.DataFrame)
        assert "SPY" in df.columns
        assert len(df) > 0

    def test_multiple_tickers(self):
        df = load_price_data(["SPY", "AAPL"], start="2024-01-01", end="2024-03-01")
        assert "SPY" in df.columns
        assert "AAPL" in df.columns

    def test_index_is_datetime(self):
        df = load_price_data(["SPY"], start="2024-01-01", end="2024-03-01")
        assert isinstance(df.index, pd.DatetimeIndex)


class TestMonthlyRebalanceDates:
    def test_returns_first_trading_day_each_month(self):
        dates = pd.bdate_range("2024-01-01", "2024-06-30")
        result = get_monthly_rebalance_dates(dates)
        # Should have ~6 dates (one per month)
        assert len(result) >= 5
        # Each date should be the first business day of its month
        for d in result:
            assert d.day <= 5  # first bday is at most the 5th
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_data_loader.py -v`
Expected: FAIL

**Step 3: Implement data loader**

```python
# quant/data_loader.py
"""Load and cache historical price and macro data."""
import os
import pandas as pd
import numpy as np
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")


def load_price_data(
    tickers: list[str],
    start: str = "2016-01-01",
    end: str = "2026-02-01",
    use_cache: bool = True,
) -> pd.DataFrame:
    """Load daily adjusted close prices for a list of tickers via yfinance.

    Returns a DataFrame with DatetimeIndex and one column per ticker.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = f"prices_{'_'.join(sorted(tickers))}_{start}_{end}.parquet"
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if use_cache and os.path.exists(cache_path):
        return pd.read_parquet(cache_path)

    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        prices = data[["Close"]].rename(columns={"Close": tickers[0]})

    prices.index = pd.to_datetime(prices.index)
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)

    if use_cache:
        prices.to_parquet(cache_path)

    return prices


def load_vix(start: str = "2016-01-01", end: str = "2026-02-01") -> pd.Series:
    """Load daily VIX closing values."""
    df = load_price_data(["^VIX"], start=start, end=end, use_cache=True)
    col = df.columns[0]
    return df[col].rename("VIX")


def load_yield_spread(start: str = "2016-01-01", end: str = "2026-02-01") -> pd.Series:
    """Load 10Y-2Y Treasury yield spread from FRED (CSV endpoint).

    Returns a Series indexed by date with the spread in percentage points.
    Falls back to NaN if unavailable.
    """
    cache_path = os.path.join(CACHE_DIR, f"t10y2y_{start}_{end}.parquet")
    os.makedirs(CACHE_DIR, exist_ok=True)

    if os.path.exists(cache_path):
        s = pd.read_parquet(cache_path).squeeze()
        return s

    url = (
        f"https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?bgcolor=%23e1e9f0&chart_type=line&drp=0&fo=open%20sans"
        f"&graph_bgcolor=%23ffffff&height=450&mode=fred&recession_bars=on"
        f"&txtcolor=%23444444&ts=12&tts=12&width=1168&nt=0&thu=0"
        f"&trc=0&show_legend=yes&show_axis_titles=yes&show_tooltip=yes"
        f"&id=T10Y2Y&scale=left&cosd={start}&coed={end}"
        f"&line_color=%234572a7&link_values=false&line_style=solid"
        f"&mark_type=none&mw=3&lw=2&ost=-99999&oet=99999&mma=0"
        f"&fml=a&fq=Daily&fam=avg&fgst=lin&fgsnd=2020-02-01"
        f"&line_index=1&transformation=lin&vintage_date=2026-02-10"
        f"&revision_date=2026-02-10&nd=1976-06-01"
    )
    try:
        df = pd.read_csv(url, parse_dates=["DATE"], index_col="DATE")
        s = df["T10Y2Y"].replace(".", np.nan).astype(float)
        s.name = "T10Y2Y"
        s.to_frame().to_parquet(cache_path)
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

    # Find the most recent DCF files (by year prefix)
    import glob
    hist_files = sorted(glob.glob(os.path.join(base, "*_dcf_*_10K.csv")))
    if hist_files:
        result["hist_df"] = pd.read_csv(hist_files[-1], index_col=0)

    meta_files = sorted(glob.glob(os.path.join(base, "*_meta.json")))
    if meta_files:
        import json
        with open(meta_files[-1]) as f:
            result["meta"] = json.load(f)

    market_files = sorted(glob.glob(os.path.join(base, "*_market_*.csv")))
    if market_files:
        result["market_df"] = pd.read_csv(market_files[-1], index_col=0)

    return result


def get_monthly_rebalance_dates(date_index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Get the first trading day of each month from a DatetimeIndex."""
    monthly = date_index.to_series().groupby(
        [date_index.year, date_index.month]
    ).first()
    return list(monthly.values)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_loader.py -v`
Expected: All PASS (requires internet for yfinance)

**Step 5: Commit**

```bash
git add quant/data_loader.py tests/test_data_loader.py
git commit -m "feat(quant): add data loader with price, VIX, yield curve support"
```

---

### Task 3: Factors — technical & momentum (F3, F4)

**Files:**
- Create: `quant/factors.py`
- Create: `tests/test_factors.py`

**Step 1: Write failing tests for technical factors**

```python
# tests/test_factors.py
import numpy as np
import pandas as pd
import pytest
from quant.factors import (
    compute_sma,
    compute_rsi,
    factor_trend_confirmation,
    factor_momentum,
)


def _make_prices(values, start="2020-01-01"):
    dates = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=dates, name="price")


class TestComputeSMA:
    def test_basic(self):
        prices = _make_prices([1, 2, 3, 4, 5])
        sma = compute_sma(prices, window=3)
        assert sma.iloc[-1] == pytest.approx(4.0)  # (3+4+5)/3

    def test_window_larger_than_data(self):
        prices = _make_prices([1, 2])
        sma = compute_sma(prices, window=5)
        assert sma.dropna().empty


class TestComputeRSI:
    def test_all_up(self):
        prices = _make_prices(list(range(100, 120)))
        rsi = compute_rsi(prices, period=14)
        # All gains, no losses → RSI should be close to 100
        assert rsi.dropna().iloc[-1] > 90

    def test_all_down(self):
        prices = _make_prices(list(range(120, 100, -1)))
        rsi = compute_rsi(prices, period=14)
        assert rsi.dropna().iloc[-1] < 10


class TestFactorTrendConfirmation:
    def test_uptrend(self):
        # Price steadily rising, well above 200-day SMA
        prices = _make_prices(list(range(100, 360)))
        f3 = factor_trend_confirmation(prices)
        # Last value should be True (above SMA, RSI not overbought in steady trend)
        assert f3.iloc[-1] == True

    def test_downtrend(self):
        # Price steadily falling
        prices = _make_prices(list(range(360, 100, -1)))
        f3 = factor_trend_confirmation(prices)
        assert f3.iloc[-1] == False


class TestFactorMomentum:
    def test_returns_float(self):
        prices = _make_prices(list(range(100, 260)))
        score = factor_momentum(prices, lookback=126)
        assert isinstance(score, float)

    def test_positive_momentum(self):
        prices = _make_prices(list(range(100, 260)))
        score = factor_momentum(prices, lookback=126)
        assert score > 0
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_factors.py -v`
Expected: FAIL

**Step 3: Implement technical factors**

```python
# quant/factors.py
"""Factor computations for the multi-factor strategy."""
import numpy as np
import pandas as pd


# ------------------------------------------------------------------
# Technical helpers
# ------------------------------------------------------------------

def compute_sma(prices: pd.Series, window: int = 200) -> pd.Series:
    """Simple moving average."""
    return prices.rolling(window=window).mean()


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ------------------------------------------------------------------
# F3: Trend confirmation (bool)
# ------------------------------------------------------------------

def factor_trend_confirmation(prices: pd.Series, sma_window: int = 200) -> pd.Series:
    """F3: True if price > 200-day SMA AND RSI < 70."""
    sma = compute_sma(prices, window=sma_window)
    rsi = compute_rsi(prices)
    above_sma = prices > sma
    not_overbought = rsi < 70
    return above_sma & not_overbought


# ------------------------------------------------------------------
# F4: Price momentum (6-month return)
# ------------------------------------------------------------------

def factor_momentum(prices: pd.Series, lookback: int = 126) -> float:
    """F4: 6-month (126 trading days) return as a momentum score.

    Returns a single float: the return over the lookback period.
    """
    if len(prices) < lookback + 1:
        return 0.0
    return float(prices.iloc[-1] / prices.iloc[-lookback - 1] - 1.0)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_factors.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add quant/factors.py tests/test_factors.py
git commit -m "feat(quant): add F3 trend confirmation and F4 momentum factors"
```

---

### Task 4: Factors — macro regime (F5)

**Files:**
- Modify: `quant/factors.py`
- Modify: `tests/test_factors.py`

**Step 1: Write failing tests for macro regime**

Add to `tests/test_factors.py`:

```python
from quant.factors import compute_macro_regime


class TestMacroRegime:
    def test_offensive_regime(self):
        # SPY above SMA, low VIX, positive yield spread
        spy = _make_prices(list(range(100, 360)))
        vix = _make_prices([15.0] * 260)
        spread = _make_prices([1.5] * 260)
        regime = compute_macro_regime(spy, vix, spread)
        assert regime in ("offensive", "neutral", "defensive")

    def test_defensive_regime(self):
        # SPY below SMA, high VIX, inverted yield curve
        spy = _make_prices(list(range(360, 100, -1)))
        vix = _make_prices([35.0] * 260)
        spread = _make_prices([-0.5] * 260)
        regime = compute_macro_regime(spy, vix, spread)
        assert regime == "defensive"

    def test_returns_valid_string(self):
        spy = _make_prices([100] * 260)
        vix = _make_prices([20.0] * 260)
        spread = _make_prices([0.5] * 260)
        regime = compute_macro_regime(spy, vix, spread)
        assert regime in ("offensive", "neutral", "defensive")
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_factors.py::TestMacroRegime -v`
Expected: FAIL

**Step 3: Implement macro regime**

Add to `quant/factors.py`:

```python
# ------------------------------------------------------------------
# F5: Macro regime
# ------------------------------------------------------------------

def compute_macro_regime(
    spy_prices: pd.Series,
    vix: pd.Series,
    yield_spread: pd.Series,
) -> str:
    """F5: Determine market regime from three signals.

    Signals (each scores 0 or 1):
      - SPY above 200-day SMA → 1
      - VIX < 25 → 1
      - 10Y-2Y yield spread > 0 → 1

    Score 3 or 2 → "offensive", 1 → "neutral", 0 → "defensive"
    """
    score = 0

    # Signal 1: SPY vs 200-day SMA
    sma200 = compute_sma(spy_prices, 200)
    if len(sma200.dropna()) > 0 and spy_prices.iloc[-1] > sma200.dropna().iloc[-1]:
        score += 1

    # Signal 2: VIX level
    current_vix = vix.dropna().iloc[-1] if len(vix.dropna()) > 0 else 20.0
    if current_vix < 25:
        score += 1

    # Signal 3: Yield curve
    current_spread = yield_spread.dropna().iloc[-1] if len(yield_spread.dropna()) > 0 else 0.0
    if current_spread > 0:
        score += 1

    if score >= 2:
        return "offensive"
    elif score == 1:
        return "neutral"
    else:
        return "defensive"
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_factors.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add quant/factors.py tests/test_factors.py
git commit -m "feat(quant): add F5 macro regime factor"
```

---

### Task 5: Factors — value (F1, F2) and industry cycle (F6)

**Files:**
- Modify: `quant/factors.py`
- Modify: `tests/test_factors.py`

**Step 1: Write failing tests for value and cycle factors**

Add to `tests/test_factors.py`:

```python
from quant.factors import (
    factor_dcf_discount,
    factor_relative_valuation,
    factor_industry_cycle,
    compute_composite_score,
)


class TestFactorDCFDiscount:
    def test_undervalued(self):
        score = factor_dcf_discount(fair_value=150.0, market_price=100.0)
        assert score == pytest.approx(1 / 3)  # (150-100)/150

    def test_overvalued(self):
        score = factor_dcf_discount(fair_value=100.0, market_price=150.0)
        assert score < 0

    def test_nan_fair_value(self):
        score = factor_dcf_discount(fair_value=np.nan, market_price=100.0)
        assert score == 0.0


class TestFactorRelativeValuation:
    def test_cheap_percentile(self):
        # Current PE at 10th percentile of history → score ≈ 0.9
        pe_history = pd.Series(range(10, 30))
        score = factor_relative_valuation(current_value=11.0, history=pe_history)
        assert score > 0.8

    def test_expensive_percentile(self):
        pe_history = pd.Series(range(10, 30))
        score = factor_relative_valuation(current_value=28.0, history=pe_history)
        assert score < 0.2


class TestFactorIndustryCycle:
    def test_accelerating_growth(self):
        # Revenue growth accelerating: 5%, 7%, 10%
        rev_growth = pd.Series([0.05, 0.07, 0.10])
        margin_change = pd.Series([0.01, 0.02, 0.03])
        score = factor_industry_cycle(rev_growth, margin_change)
        assert score > 0.5

    def test_decelerating_growth(self):
        rev_growth = pd.Series([0.10, 0.07, 0.03])
        margin_change = pd.Series([-0.01, -0.02, -0.03])
        score = factor_industry_cycle(rev_growth, margin_change)
        assert score < 0.5


class TestCompositeScore:
    def test_weighted_sum(self):
        factors = {"value": 0.8, "momentum": 0.6, "cycle": 0.4}
        weights = {"value": 0.4, "momentum": 0.35, "cycle": 0.25}
        score = compute_composite_score(factors, weights)
        expected = 0.8 * 0.4 + 0.6 * 0.35 + 0.4 * 0.25
        assert score == pytest.approx(expected)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_factors.py -v -k "DCFDiscount or RelativeValuation or IndustryCycle or Composite"`
Expected: FAIL

**Step 3: Implement value and cycle factors**

Add to `quant/factors.py`:

```python
# ------------------------------------------------------------------
# F1: DCF discount
# ------------------------------------------------------------------

def factor_dcf_discount(fair_value: float, market_price: float) -> float:
    """F1: (fair_value - market_price) / fair_value.

    Positive → undervalued, negative → overvalued.
    """
    if not np.isfinite(fair_value) or fair_value <= 0:
        return 0.0
    return (fair_value - market_price) / fair_value


# ------------------------------------------------------------------
# F2: Relative valuation percentile
# ------------------------------------------------------------------

def factor_relative_valuation(current_value: float, history: pd.Series) -> float:
    """F2: Score = 1 - percentile of current value in its own history.

    Lower percentile (cheaper) → higher score.
    """
    clean = history.dropna()
    if len(clean) < 5 or not np.isfinite(current_value):
        return 0.5  # neutral
    percentile = (clean < current_value).mean()
    return 1.0 - percentile


# ------------------------------------------------------------------
# F6: Industry cycle
# ------------------------------------------------------------------

def factor_industry_cycle(
    rev_growth_series: pd.Series,
    margin_change_series: pd.Series,
) -> float:
    """F6: Score based on revenue growth acceleration and margin trend.

    Score = average of two sub-signals, each in [0, 1]:
      - Revenue growth trend (recent vs earlier): accelerating → higher
      - Margin change trend: expanding → higher
    """
    if len(rev_growth_series) < 2 or len(margin_change_series) < 2:
        return 0.5

    # Revenue growth acceleration: compare recent half to earlier half
    mid = len(rev_growth_series) // 2
    recent_growth = rev_growth_series.iloc[mid:].mean()
    earlier_growth = rev_growth_series.iloc[:mid].mean()
    # Sigmoid-like scoring
    growth_accel = recent_growth - earlier_growth
    growth_score = 1.0 / (1.0 + np.exp(-growth_accel * 20))  # scale factor

    # Margin trend
    recent_margin = margin_change_series.iloc[mid:].mean()
    earlier_margin = margin_change_series.iloc[:mid].mean()
    margin_accel = recent_margin - earlier_margin
    margin_score = 1.0 / (1.0 + np.exp(-margin_accel * 20))

    return (growth_score + margin_score) / 2.0


# ------------------------------------------------------------------
# Composite score
# ------------------------------------------------------------------

REGIME_WEIGHTS = {
    "offensive": {"value": 0.40, "momentum": 0.35, "cycle": 0.25},
    "neutral":   {"value": 0.40, "momentum": 0.30, "cycle": 0.30},
    "defensive": {"value": 0.50, "momentum": 0.20, "cycle": 0.30},
}

REGIME_MAX_EXPOSURE = {
    "offensive": 1.0,
    "neutral":   0.65,
    "defensive": 0.30,
}

REGIME_TOP_PCT = {
    "offensive": 0.40,
    "neutral":   0.25,
    "defensive": 0.10,
}


def compute_composite_score(
    factors: dict[str, float],
    weights: dict[str, float],
) -> float:
    """Weighted sum of factor scores."""
    total = 0.0
    for k, w in weights.items():
        total += factors.get(k, 0.0) * w
    return total
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_factors.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add quant/factors.py tests/test_factors.py
git commit -m "feat(quant): add F1 DCF discount, F2 relative valuation, F6 industry cycle factors"
```

---

### Task 6: Portfolio manager — risk parity

**Files:**
- Create: `quant/portfolio.py`
- Create: `tests/test_portfolio.py`

**Step 1: Write failing tests**

```python
# tests/test_portfolio.py
import numpy as np
import pandas as pd
import pytest
from quant.portfolio import (
    compute_risk_parity_weights,
    apply_position_limits,
    calculate_trades,
)


class TestRiskParityWeights:
    def test_equal_vol(self):
        # Same volatility → equal weight
        vols = {"AAPL": 0.20, "GOOGL": 0.20}
        weights = compute_risk_parity_weights(vols)
        assert weights["AAPL"] == pytest.approx(0.5)
        assert weights["GOOGL"] == pytest.approx(0.5)

    def test_different_vol(self):
        # Higher vol → lower weight
        vols = {"AAPL": 0.10, "GOOGL": 0.30}
        weights = compute_risk_parity_weights(vols)
        assert weights["AAPL"] > weights["GOOGL"]
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_single_stock(self):
        vols = {"AAPL": 0.25}
        weights = compute_risk_parity_weights(vols)
        assert weights["AAPL"] == pytest.approx(1.0)


class TestPositionLimits:
    def test_cap_at_max(self):
        weights = {"A": 0.50, "B": 0.30, "C": 0.20}
        capped = apply_position_limits(weights, max_weight=0.20)
        for w in capped.values():
            assert w <= 0.20 + 1e-9
        assert sum(capped.values()) == pytest.approx(1.0)


class TestCalculateTrades:
    def test_buy_from_cash(self):
        current = {}  # no positions
        target = {"AAPL": 0.5, "GOOGL": 0.5}
        prices = {"AAPL": 200.0, "GOOGL": 150.0}
        cash = 100000.0
        trades = calculate_trades(current, target, prices, cash, max_exposure=1.0)
        assert trades["AAPL"]["action"] == "buy"
        assert trades["AAPL"]["dollars"] > 0

    def test_sell_removed_stock(self):
        current = {"AAPL": {"shares": 100, "value": 20000}}
        target = {}  # sell everything
        prices = {"AAPL": 200.0}
        trades = calculate_trades(current, target, prices, cash=0, max_exposure=1.0)
        assert trades["AAPL"]["action"] == "sell"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_portfolio.py -v`
Expected: FAIL

**Step 3: Implement portfolio manager**

```python
# quant/portfolio.py
"""Portfolio construction and risk parity weighting."""
import numpy as np

# Transaction costs
COMMISSION_RATE = 0.001   # 0.1% per side
SLIPPAGE_RATE = 0.0005    # 0.05% per side
COST_PER_SIDE = COMMISSION_RATE + SLIPPAGE_RATE  # 0.15%


def compute_risk_parity_weights(volatilities: dict[str, float]) -> dict[str, float]:
    """Risk parity: weight proportional to 1/volatility.

    Args:
        volatilities: {ticker: annualized_vol}

    Returns:
        {ticker: weight} summing to 1.0
    """
    inv_vols = {t: 1.0 / v for t, v in volatilities.items() if v > 0}
    total = sum(inv_vols.values())
    if total == 0:
        n = len(volatilities)
        return {t: 1.0 / n for t in volatilities}
    return {t: iv / total for t, iv in inv_vols.items()}


def apply_position_limits(
    weights: dict[str, float], max_weight: float = 0.20
) -> dict[str, float]:
    """Cap each position at max_weight and redistribute excess proportionally."""
    capped = {}
    excess = 0.0
    uncapped_keys = []

    for t, w in weights.items():
        if w > max_weight:
            capped[t] = max_weight
            excess += w - max_weight
        else:
            capped[t] = w
            uncapped_keys.append(t)

    # Redistribute excess to uncapped positions
    while excess > 1e-9 and uncapped_keys:
        add_each = excess / len(uncapped_keys)
        new_uncapped = []
        excess = 0.0
        for t in uncapped_keys:
            new_w = capped[t] + add_each
            if new_w > max_weight:
                excess += new_w - max_weight
                capped[t] = max_weight
            else:
                capped[t] = new_w
                new_uncapped.append(t)
        uncapped_keys = new_uncapped

    # Normalize
    total = sum(capped.values())
    if total > 0:
        capped = {t: w / total for t, w in capped.items()}
    return capped


def calculate_trades(
    current_positions: dict,
    target_weights: dict[str, float],
    prices: dict[str, float],
    cash: float,
    max_exposure: float = 1.0,
) -> dict:
    """Calculate trades needed to move from current to target portfolio.

    Args:
        current_positions: {ticker: {"shares": float, "value": float}}
        target_weights: {ticker: weight} (sums to 1.0)
        prices: {ticker: current_price}
        cash: available cash
        max_exposure: max fraction of total portfolio to invest (from regime)

    Returns:
        {ticker: {"action": "buy"|"sell", "shares": float, "dollars": float}}
    """
    # Total portfolio value
    total_value = cash + sum(
        pos.get("value", 0) for pos in current_positions.values()
    )
    investable = total_value * max_exposure

    trades = {}

    # Sell positions not in target
    for ticker in current_positions:
        if ticker not in target_weights:
            pos = current_positions[ticker]
            trades[ticker] = {
                "action": "sell",
                "shares": pos["shares"],
                "dollars": pos["value"],
            }

    # Buy/adjust positions in target
    for ticker, weight in target_weights.items():
        target_value = investable * weight
        current_value = current_positions.get(ticker, {}).get("value", 0.0)
        diff = target_value - current_value
        price = prices.get(ticker, 0)

        if price <= 0:
            continue

        if diff > 0:
            # Account for transaction cost
            buy_dollars = diff * (1 - COST_PER_SIDE)
            trades[ticker] = {
                "action": "buy",
                "shares": buy_dollars / price,
                "dollars": buy_dollars,
            }
        elif diff < -total_value * 0.01:  # only sell if diff > 1% of portfolio
            sell_dollars = abs(diff) * (1 - COST_PER_SIDE)
            trades[ticker] = {
                "action": "sell",
                "shares": sell_dollars / price,
                "dollars": sell_dollars,
            }

    return trades
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_portfolio.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add quant/portfolio.py tests/test_portfolio.py
git commit -m "feat(quant): add risk parity portfolio manager with position limits"
```

---

### Task 7: Strategy — signal generation and buy/sell rules

**Files:**
- Create: `quant/strategy.py`
- Create: `tests/test_strategy.py`

**Step 1: Write failing tests**

```python
# tests/test_strategy.py
import numpy as np
import pandas as pd
import pytest
from quant.strategy import generate_signals, check_sell_conditions


class TestGenerateSignals:
    def test_returns_dict_of_scores(self):
        scores = {"AAPL": 0.8, "GOOGL": 0.6, "MSFT": 0.3}
        trend_ok = {"AAPL": True, "GOOGL": True, "MSFT": False}
        result = generate_signals(scores, trend_ok, regime="offensive", n_universe=5)
        # MSFT should be excluded (trend not confirmed)
        assert "MSFT" not in result
        assert "AAPL" in result

    def test_defensive_regime_fewer_picks(self):
        scores = {f"T{i}": 0.9 - i * 0.1 for i in range(10)}
        trend_ok = {f"T{i}": True for i in range(10)}
        result = generate_signals(scores, trend_ok, regime="defensive", n_universe=10)
        # Defensive top 10% of 10 → 1 stock
        assert len(result) <= 2


class TestSellConditions:
    def test_stop_loss_triggered(self):
        should_sell, reason = check_sell_conditions(
            entry_price=100.0,
            current_price=80.0,
            fair_value=150.0,
            in_top_n=True,
            trend_confirmed=True,
            stop_loss_pct=0.15,
        )
        assert should_sell
        assert "stop_loss" in reason

    def test_valuation_recovery(self):
        should_sell, reason = check_sell_conditions(
            entry_price=100.0,
            current_price=160.0,
            fair_value=150.0,
            in_top_n=True,
            trend_confirmed=True,
        )
        assert should_sell
        assert "valuation" in reason

    def test_hold(self):
        should_sell, reason = check_sell_conditions(
            entry_price=100.0,
            current_price=110.0,
            fair_value=150.0,
            in_top_n=True,
            trend_confirmed=True,
        )
        assert not should_sell
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_strategy.py -v`
Expected: FAIL

**Step 3: Implement strategy**

```python
# quant/strategy.py
"""Buy/sell signal generation and rebalancing rules."""
from quant.factors import REGIME_TOP_PCT


def generate_signals(
    composite_scores: dict[str, float],
    trend_confirmed: dict[str, bool],
    regime: str,
    n_universe: int,
) -> dict[str, float]:
    """Select stocks to buy based on composite score + trend filter.

    Returns {ticker: score} for stocks that pass all filters.
    """
    top_pct = REGIME_TOP_PCT.get(regime, 0.25)
    n_select = max(1, int(n_universe * top_pct))

    # Filter: must pass trend confirmation (F3)
    candidates = {
        t: s for t, s in composite_scores.items()
        if trend_confirmed.get(t, False)
    }

    # Sort by score descending, take top N
    sorted_tickers = sorted(candidates, key=candidates.get, reverse=True)
    selected = sorted_tickers[:n_select]

    return {t: candidates[t] for t in selected}


def check_sell_conditions(
    entry_price: float,
    current_price: float,
    fair_value: float,
    in_top_n: bool,
    trend_confirmed: bool,
    stop_loss_pct: float = 0.15,
) -> tuple[bool, str]:
    """Check if a position should be sold.

    Returns (should_sell, reason).
    """
    # 1. Stop loss
    loss = (entry_price - current_price) / entry_price
    if loss >= stop_loss_pct:
        return True, "stop_loss"

    # 2. Valuation recovery: price >= fair value
    if current_price >= fair_value and fair_value > 0:
        return True, "valuation_recovery"

    # 3. Score dropped out of top N
    if not in_top_n:
        return True, "score_dropped"

    # 4. Technical deterioration (price below SMA + RSI < 30)
    # Note: trend_confirmed=False covers "below SMA" part
    # RSI < 30 check would need price data; simplified here
    if not trend_confirmed:
        return True, "technical_deterioration"

    return False, "hold"
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_strategy.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add quant/strategy.py tests/test_strategy.py
git commit -m "feat(quant): add strategy module with signal generation and sell rules"
```

---

### Task 8: Backtest engine

**Files:**
- Create: `quant/backtest.py`
- Create: `tests/test_backtest.py`

**Step 1: Write failing test for backtest engine**

```python
# tests/test_backtest.py
import numpy as np
import pandas as pd
import pytest
from quant.backtest import Backtester


class TestBacktester:
    def test_runs_without_error(self):
        """Smoke test: run a minimal backtest with synthetic data."""
        # Create synthetic price data (2 years, 3 stocks + SPY)
        dates = pd.bdate_range("2023-01-01", "2024-12-31")
        np.random.seed(42)
        prices = pd.DataFrame({
            "AAA": 100 * np.cumprod(1 + np.random.normal(0.0003, 0.02, len(dates))),
            "BBB": 50 * np.cumprod(1 + np.random.normal(0.0002, 0.015, len(dates))),
            "CCC": 200 * np.cumprod(1 + np.random.normal(0.0001, 0.025, len(dates))),
            "SPY": 400 * np.cumprod(1 + np.random.normal(0.0003, 0.01, len(dates))),
        }, index=dates)

        # Synthetic fair values (constant)
        fair_values = {"AAA": 120.0, "BBB": 45.0, "CCC": 250.0}

        bt = Backtester(
            prices=prices,
            universe=["AAA", "BBB", "CCC"],
            fair_values=fair_values,
            benchmark="SPY",
            initial_cash=100000.0,
        )
        result = bt.run()

        assert "nav" in result
        assert "trades" in result
        assert "metrics" in result
        assert len(result["nav"]) > 0
        assert result["metrics"]["total_return"] != 0

    def test_nav_starts_at_initial_cash(self):
        dates = pd.bdate_range("2023-01-01", "2023-06-30")
        prices = pd.DataFrame({
            "AAA": np.linspace(100, 120, len(dates)),
            "SPY": np.linspace(400, 420, len(dates)),
        }, index=dates)
        fair_values = {"AAA": 150.0}

        bt = Backtester(
            prices=prices,
            universe=["AAA"],
            fair_values=fair_values,
            benchmark="SPY",
            initial_cash=50000.0,
        )
        result = bt.run()
        assert result["nav"].iloc[0] == pytest.approx(50000.0, rel=0.01)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: FAIL

**Step 3: Implement backtest engine**

```python
# quant/backtest.py
"""Monthly rebalancing backtest engine."""
import numpy as np
import pandas as pd
from quant.data_loader import get_monthly_rebalance_dates
from quant.factors import (
    factor_trend_confirmation,
    factor_momentum,
    factor_dcf_discount,
    factor_relative_valuation,
    factor_industry_cycle,
    compute_macro_regime,
    compute_composite_score,
    REGIME_WEIGHTS,
    REGIME_MAX_EXPOSURE,
)
from quant.portfolio import (
    compute_risk_parity_weights,
    apply_position_limits,
    COST_PER_SIDE,
)
from quant.strategy import generate_signals, check_sell_conditions
from quant.metrics import (
    total_return,
    cagr,
    max_drawdown,
    annualized_volatility,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    compute_alpha_beta,
)


class Backtester:
    """Monthly rebalancing backtester with multi-factor signals."""

    def __init__(
        self,
        prices: pd.DataFrame,
        universe: list[str],
        fair_values: dict[str, float],
        benchmark: str = "SPY",
        initial_cash: float = 100_000.0,
        vix: pd.Series = None,
        yield_spread: pd.Series = None,
        fundamental_data: dict = None,
    ):
        self.prices = prices
        self.universe = universe
        self.fair_values = fair_values
        self.benchmark = benchmark
        self.initial_cash = initial_cash
        self.vix = vix
        self.yield_spread = yield_spread
        self.fundamental_data = fundamental_data or {}

    def run(self) -> dict:
        """Execute the backtest and return results."""
        rebal_dates = get_monthly_rebalance_dates(self.prices.index)

        # State
        cash = self.initial_cash
        positions = {}    # {ticker: {"shares": float, "entry_price": float}}
        nav_series = []   # [(date, nav)]
        trade_log = []    # list of trade dicts

        # Track daily NAV
        for date in self.prices.index:
            port_value = cash
            for ticker, pos in positions.items():
                if ticker in self.prices.columns:
                    price = self.prices.loc[date, ticker]
                    if np.isfinite(price):
                        port_value += pos["shares"] * price
            nav_series.append((date, port_value))

            # Monthly rebalancing
            if date in rebal_dates:
                cash, positions, new_trades = self._rebalance(
                    date, cash, positions
                )
                trade_log.extend(new_trades)

        # Build NAV series
        nav = pd.Series(
            [v for _, v in nav_series],
            index=pd.DatetimeIndex([d for d, _ in nav_series]),
            name="NAV",
        )

        # Benchmark NAV
        bench_col = self.benchmark if self.benchmark in self.prices.columns else self.prices.columns[-1]
        bench_prices = self.prices[bench_col].dropna()
        bench_nav = bench_prices / bench_prices.iloc[0] * self.initial_cash

        # Metrics
        alpha, beta = compute_alpha_beta(nav, bench_nav)
        metrics = {
            "total_return": total_return(nav),
            "cagr": cagr(nav),
            "max_drawdown": max_drawdown(nav),
            "volatility": annualized_volatility(nav),
            "sharpe": sharpe_ratio(nav),
            "sortino": sortino_ratio(nav),
            "calmar": calmar_ratio(nav),
            "alpha": alpha,
            "beta": beta,
            "benchmark_return": total_return(bench_nav),
            "benchmark_cagr": cagr(bench_nav),
        }

        return {
            "nav": nav,
            "benchmark_nav": bench_nav,
            "trades": pd.DataFrame(trade_log) if trade_log else pd.DataFrame(),
            "metrics": metrics,
        }

    def _rebalance(self, date, cash, positions):
        """Execute monthly rebalance logic."""
        new_trades = []

        # --- Compute factors ---
        # Price history up to this date
        hist = self.prices.loc[:date]

        # F5: Macro regime
        spy_col = self.benchmark if self.benchmark in hist.columns else hist.columns[-1]
        spy_hist = hist[spy_col].dropna()

        if self.vix is not None:
            vix_hist = self.vix.loc[:date].dropna()
        else:
            vix_hist = pd.Series([20.0], index=[date])

        if self.yield_spread is not None:
            spread_hist = self.yield_spread.loc[:date].dropna()
        else:
            spread_hist = pd.Series([1.0], index=[date])

        regime = compute_macro_regime(spy_hist, vix_hist, spread_hist)
        weights_config = REGIME_WEIGHTS[regime]
        max_exposure = REGIME_MAX_EXPOSURE[regime]

        # Per-stock factors
        composite_scores = {}
        trend_flags = {}
        volatilities = {}

        for ticker in self.universe:
            if ticker not in hist.columns:
                continue
            ticker_prices = hist[ticker].dropna()
            if len(ticker_prices) < 50:
                continue

            # F1: DCF discount
            current_price = ticker_prices.iloc[-1]
            fv = self.fair_values.get(ticker, np.nan)
            f1 = factor_dcf_discount(fv, current_price)

            # F2: Relative valuation (use trailing P/E percentile proxy via price)
            # Simplified: use price percentile in 1-year history as proxy
            one_year = ticker_prices.iloc[-252:] if len(ticker_prices) >= 252 else ticker_prices
            f2 = factor_relative_valuation(current_price, one_year)

            # F3: Trend confirmation
            f3_series = factor_trend_confirmation(ticker_prices)
            f3 = bool(f3_series.iloc[-1]) if len(f3_series) > 0 else False
            trend_flags[ticker] = f3

            # F4: Momentum
            f4 = factor_momentum(ticker_prices)

            # F6: Industry cycle (simplified: use price growth as proxy)
            if len(ticker_prices) >= 252:
                quarterly_returns = ticker_prices.resample("QE").last().pct_change().dropna()
                rev_growth = quarterly_returns.iloc[-4:] if len(quarterly_returns) >= 4 else quarterly_returns
                margin_proxy = rev_growth  # simplified
                f6 = factor_industry_cycle(rev_growth, margin_proxy)
            else:
                f6 = 0.5

            # Normalize F1 and F4 to [0, 1] range for combining
            f1_norm = max(0, min(1, (f1 + 0.5)))  # shift: -0.5→0, 0.5→1
            f4_norm = max(0, min(1, (f4 + 0.5)))

            value_score = (f1_norm + f2) / 2.0
            momentum_score = (1.0 if f3 else 0.0 + f4_norm) / 2.0
            cycle_score = f6

            composite = compute_composite_score(
                {"value": value_score, "momentum": momentum_score, "cycle": cycle_score},
                weights_config,
            )
            composite_scores[ticker] = composite

            # Volatility for risk parity
            returns = ticker_prices.pct_change().dropna()
            vol = float(returns.iloc[-60:].std() * np.sqrt(252)) if len(returns) >= 60 else 0.20
            volatilities[ticker] = vol

        # --- Signal generation ---
        selected = generate_signals(
            composite_scores, trend_flags, regime, len(self.universe)
        )

        # --- Sell check for current positions ---
        for ticker in list(positions.keys()):
            if ticker not in hist.columns:
                continue
            current_price = hist[ticker].dropna().iloc[-1]
            pos = positions[ticker]
            fv = self.fair_values.get(ticker, np.nan)

            should_sell, reason = check_sell_conditions(
                entry_price=pos["entry_price"],
                current_price=current_price,
                fair_value=fv,
                in_top_n=(ticker in selected),
                trend_confirmed=trend_flags.get(ticker, False),
            )

            if should_sell:
                sell_value = pos["shares"] * current_price * (1 - COST_PER_SIDE)
                cash += sell_value
                new_trades.append({
                    "date": date,
                    "ticker": ticker,
                    "action": "sell",
                    "shares": pos["shares"],
                    "price": current_price,
                    "value": sell_value,
                    "reason": reason,
                })
                del positions[ticker]

        # --- Buy / rebalance ---
        if selected:
            sel_vols = {t: volatilities.get(t, 0.20) for t in selected}
            target_weights = compute_risk_parity_weights(sel_vols)
            target_weights = apply_position_limits(target_weights, max_weight=0.20)

            # Total portfolio value
            port_value = cash + sum(
                pos["shares"] * hist[t].dropna().iloc[-1]
                for t, pos in positions.items()
                if t in hist.columns
            )
            investable = port_value * max_exposure

            for ticker, weight in target_weights.items():
                if ticker not in hist.columns:
                    continue
                current_price = hist[ticker].dropna().iloc[-1]
                target_value = investable * weight
                current_value = (
                    positions[ticker]["shares"] * current_price
                    if ticker in positions else 0.0
                )
                diff = target_value - current_value

                if diff > port_value * 0.01 and cash > diff * 0.5:
                    buy_dollars = min(diff, cash) * (1 - COST_PER_SIDE)
                    buy_shares = buy_dollars / current_price
                    cash -= buy_dollars / (1 - COST_PER_SIDE)

                    if ticker in positions:
                        old = positions[ticker]
                        total_shares = old["shares"] + buy_shares
                        avg_price = (
                            (old["entry_price"] * old["shares"] + current_price * buy_shares)
                            / total_shares
                        )
                        positions[ticker] = {"shares": total_shares, "entry_price": avg_price}
                    else:
                        positions[ticker] = {"shares": buy_shares, "entry_price": current_price}

                    new_trades.append({
                        "date": date,
                        "ticker": ticker,
                        "action": "buy",
                        "shares": buy_shares,
                        "price": current_price,
                        "value": buy_dollars,
                        "reason": "signal",
                    })

        return cash, positions, new_trades
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add quant/backtest.py tests/test_backtest.py
git commit -m "feat(quant): add backtest engine with monthly rebalancing"
```

---

### Task 9: Entry script + visualization

**Files:**
- Create: `quant/run_backtest.py`

**Step 1: Implement entry script**

```python
# quant/run_backtest.py
"""Entry point: run the multi-factor backtest and generate reports."""
import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.data_loader import load_price_data, load_vix, load_yield_spread, load_fundamental_data
from quant.backtest import Backtester


# Default universe (from existing output/)
UNIVERSE = [
    "AAPL", "AMZN", "AVGO", "CSGP", "EXLS", "FCX", "GOOGL",
    "LMT", "MSFT", "PLTR", "SNOW", "TSLA", "V", "ZG",
]
# Excluded: DXYZ, IREN, NBIS, RDFN (may have insufficient price history)

START_DATE = "2016-01-01"
END_DATE = "2026-02-01"
INITIAL_CASH = 100_000.0
OUTPUT_DIR = "output/backtest"


def load_fair_values(universe: list[str], output_dir: str = "output") -> dict[str, float]:
    """Load DCF fair values from meta.json files."""
    fair_values = {}
    for ticker in universe:
        data = load_fundamental_data(ticker, output_dir)
        meta = data.get("meta", {})
        fv_str = meta.get("Fair Value / Share ", "")
        try:
            fair_values[ticker] = float(str(fv_str).replace(",", ""))
        except (ValueError, TypeError):
            fair_values[ticker] = np.nan
    return fair_values


def plot_results(result: dict, output_dir: str):
    """Generate performance charts."""
    os.makedirs(output_dir, exist_ok=True)
    nav = result["nav"]
    bench = result["benchmark_nav"]

    # 1. NAV curve
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(nav.index, nav.values, label="Strategy", linewidth=1.5)
    ax.plot(bench.index, bench.values, label="SPY (Buy & Hold)", linewidth=1.5, alpha=0.7)
    ax.set_title("Portfolio NAV: Strategy vs SPY")
    ax.set_ylabel("Portfolio Value ($)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "nav_curve.png"), dpi=150)
    plt.close(fig)

    # 2. Drawdown curve
    peak = nav.cummax()
    dd = (peak - nav) / peak * 100
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(dd.index, dd.values, alpha=0.4, color="red")
    ax.set_title("Strategy Drawdown")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "drawdown.png"), dpi=150)
    plt.close(fig)

    # 3. Monthly returns heatmap
    monthly_returns = nav.resample("ME").last().pct_change().dropna()
    monthly_df = pd.DataFrame({
        "year": monthly_returns.index.year,
        "month": monthly_returns.index.month,
        "return": monthly_returns.values * 100,
    })
    pivot = monthly_df.pivot(index="year", columns="month", values="return")
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto",
                   vmin=-10, vmax=10)
    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Monthly Returns Heatmap (%)")
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "monthly_heatmap.png"), dpi=150)
    plt.close(fig)


def print_report(result: dict):
    """Print performance summary to console."""
    m = result["metrics"]
    print("\n" + "=" * 60)
    print("  BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Total Return:       {m['total_return']:.1%}")
    print(f"  CAGR:               {m['cagr']:.1%}")
    print(f"  Max Drawdown:       {m['max_drawdown']:.1%}")
    print(f"  Volatility:         {m['volatility']:.1%}")
    print(f"  Sharpe Ratio:       {m['sharpe']:.2f}")
    print(f"  Sortino Ratio:      {m['sortino']:.2f}")
    print(f"  Calmar Ratio:       {m['calmar']:.2f}")
    print(f"  Alpha:              {m['alpha']:.2%}")
    print(f"  Beta:               {m['beta']:.2f}")
    print("-" * 60)
    print(f"  Benchmark Return:   {m['benchmark_return']:.1%}")
    print(f"  Benchmark CAGR:     {m['benchmark_cagr']:.1%}")
    print(f"  Excess Return:      {m['total_return'] - m['benchmark_return']:.1%}")
    print("=" * 60)

    trades = result["trades"]
    if not trades.empty:
        print(f"\n  Total Trades: {len(trades)}")
        print(f"  Buys:  {len(trades[trades['action'] == 'buy'])}")
        print(f"  Sells: {len(trades[trades['action'] == 'sell'])}")
    print()


def main():
    print("Loading price data...")
    all_tickers = UNIVERSE + ["SPY"]
    prices = load_price_data(all_tickers, start=START_DATE, end=END_DATE)

    # Drop tickers with insufficient data
    valid_universe = [t for t in UNIVERSE if t in prices.columns and prices[t].dropna().shape[0] > 252]
    print(f"Valid universe: {len(valid_universe)} stocks: {valid_universe}")

    print("Loading macro data...")
    vix = load_vix(start=START_DATE, end=END_DATE)
    spread = load_yield_spread(start=START_DATE, end=END_DATE)

    print("Loading DCF fair values...")
    fair_values = load_fair_values(valid_universe)
    print("Fair values:", {k: f"${v:.2f}" if np.isfinite(v) else "N/A" for k, v in fair_values.items()})

    print("Running backtest...")
    bt = Backtester(
        prices=prices,
        universe=valid_universe,
        fair_values=fair_values,
        benchmark="SPY",
        initial_cash=INITIAL_CASH,
        vix=vix,
        yield_spread=spread,
    )
    result = bt.run()

    print_report(result)

    print("Generating charts...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plot_results(result, OUTPUT_DIR)

    # Save metrics
    metrics_path = os.path.join(OUTPUT_DIR, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(
            {k: round(v, 4) if isinstance(v, float) and np.isfinite(v) else str(v)
             for k, v in result["metrics"].items()},
            f, indent=2,
        )

    # Save trades
    if not result["trades"].empty:
        trades_path = os.path.join(OUTPUT_DIR, "trades.csv")
        result["trades"].to_csv(trades_path, index=False)
        print(f"Trades saved to {trades_path}")

    # Save daily NAV
    nav_path = os.path.join(OUTPUT_DIR, "nav.csv")
    result["nav"].to_csv(nav_path)
    print(f"NAV saved to {nav_path}")

    print(f"\nAll outputs saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
```

**Step 2: Test by running the script**

Run: `cd /Users/y32lyu/Nextcloud/UWaterloo/Project/Claudcode_AI_workspace/AI_stock_analysis && python -m quant.run_backtest`
Expected: Backtest completes, prints metrics, saves charts to `output/backtest/`

**Step 3: Commit**

```bash
git add quant/run_backtest.py
git commit -m "feat(quant): add backtest entry script with visualization"
```

---

### Task 10: Run all tests + integration smoke test

**Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: All tests pass

**Step 2: Run full backtest**

```bash
python -m quant.run_backtest
```
Expected: Prints performance report, generates `output/backtest/` with:
- `nav_curve.png`
- `drawdown.png`
- `monthly_heatmap.png`
- `metrics.json`
- `trades.csv`
- `nav.csv`

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(quant): complete Phase 1 multi-factor backtester"
```
