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
