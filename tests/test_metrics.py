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
        # 252 trading days ~ 1 year
        nav = _make_nav([100] + [110] * 251)
        result = cagr(nav)
        assert result == pytest.approx(0.10, abs=0.02)


class TestMaxDrawdown:
    def test_simple_drawdown(self):
        nav = _make_nav([100, 120, 90, 110])
        # peak=120, trough=90 -> dd = 30/120 = 0.25
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
        # If all returns are positive, downside deviation is ~0 -> inf or very large
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
