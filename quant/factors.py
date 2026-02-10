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
      - SPY above 200-day SMA -> 1
      - VIX < 25 -> 1
      - 10Y-2Y yield spread > 0 -> 1

    Score 3 or 2 -> "offensive", 1 -> "neutral", 0 -> "defensive"
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


# ------------------------------------------------------------------
# F1: DCF discount
# ------------------------------------------------------------------

def factor_dcf_discount(fair_value: float, market_price: float) -> float:
    """F1: (fair_value - market_price) / fair_value.

    Positive -> undervalued, negative -> overvalued.
    """
    if not np.isfinite(fair_value) or fair_value <= 0:
        return 0.0
    return (fair_value - market_price) / fair_value


# ------------------------------------------------------------------
# F2: Relative valuation percentile
# ------------------------------------------------------------------

def factor_relative_valuation(current_value: float, history: pd.Series) -> float:
    """F2: Score = 1 - percentile of current value in its own history.

    Lower percentile (cheaper) -> higher score.
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
      - Revenue growth trend (recent vs earlier): accelerating -> higher
      - Margin change trend: expanding -> higher
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
    factors: dict,
    weights: dict,
) -> float:
    """Weighted sum of factor scores."""
    total = 0.0
    for k, w in weights.items():
        total += factors.get(k, 0.0) * w
    return total
