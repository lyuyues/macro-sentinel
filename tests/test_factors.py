import numpy as np
import pandas as pd
import pytest
from quant.factors import (
    compute_sma,
    compute_rsi,
    factor_trend_confirmation,
    factor_momentum,
    compute_macro_regime,
    factor_dcf_discount,
    factor_relative_valuation,
    factor_industry_cycle,
    compute_composite_score,
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
        # All gains, no losses -> RSI should be close to 100
        assert rsi.dropna().iloc[-1] > 90

    def test_all_down(self):
        prices = _make_prices(list(range(120, 100, -1)))
        rsi = compute_rsi(prices, period=14)
        assert rsi.dropna().iloc[-1] < 10


class TestFactorTrendConfirmation:
    def test_uptrend(self):
        # Price generally rising with noise (so RSI stays below 70)
        np.random.seed(42)
        noise = np.random.normal(0, 2, 300)
        trend = np.linspace(100, 250, 300) + noise
        prices = _make_prices(trend.tolist())
        f3 = factor_trend_confirmation(prices)
        # Last value should be True (above SMA, RSI not overbought)
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


# === F5: Macro regime ===

class TestMacroRegime:
    def test_offensive_regime(self):
        # SPY above SMA, low VIX, positive yield spread
        np.random.seed(42)
        spy = _make_prices((np.linspace(100, 250, 260) + np.random.normal(0, 2, 260)).tolist())
        vix = _make_prices([15.0] * 260)
        spread = _make_prices([1.5] * 260)
        regime = compute_macro_regime(spy, vix, spread)
        assert regime == "offensive"

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


# === F1: DCF discount ===

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


# === F2: Relative valuation ===

class TestFactorRelativeValuation:
    def test_cheap_percentile(self):
        pe_history = pd.Series(range(10, 30))
        score = factor_relative_valuation(current_value=11.0, history=pe_history)
        assert score > 0.8

    def test_expensive_percentile(self):
        pe_history = pd.Series(range(10, 30))
        score = factor_relative_valuation(current_value=28.0, history=pe_history)
        assert score < 0.2


# === F6: Industry cycle ===

class TestFactorIndustryCycle:
    def test_accelerating_growth(self):
        rev_growth = pd.Series([0.05, 0.07, 0.10])
        margin_change = pd.Series([0.01, 0.02, 0.03])
        score = factor_industry_cycle(rev_growth, margin_change)
        assert score > 0.5

    def test_decelerating_growth(self):
        rev_growth = pd.Series([0.10, 0.07, 0.03])
        margin_change = pd.Series([-0.01, -0.02, -0.03])
        score = factor_industry_cycle(rev_growth, margin_change)
        assert score < 0.5


# === Composite score ===

class TestCompositeScore:
    def test_weighted_sum(self):
        factors = {"value": 0.8, "momentum": 0.6, "cycle": 0.4}
        weights = {"value": 0.4, "momentum": 0.35, "cycle": 0.25}
        score = compute_composite_score(factors, weights)
        expected = 0.8 * 0.4 + 0.6 * 0.35 + 0.4 * 0.25
        assert score == pytest.approx(expected)
