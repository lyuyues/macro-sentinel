import numpy as np
import pandas as pd
import pytest
from quant.backtest import Backtester


class TestBacktester:
    def test_runs_without_error(self):
        """Smoke test: run a minimal backtest with synthetic data."""
        dates = pd.bdate_range("2023-01-01", "2024-12-31")
        np.random.seed(42)
        prices = pd.DataFrame({
            "AAA": 100 * np.cumprod(1 + np.random.normal(0.0003, 0.02, len(dates))),
            "BBB": 50 * np.cumprod(1 + np.random.normal(0.0002, 0.015, len(dates))),
            "CCC": 200 * np.cumprod(1 + np.random.normal(0.0001, 0.025, len(dates))),
            "SPY": 400 * np.cumprod(1 + np.random.normal(0.0003, 0.01, len(dates))),
        }, index=dates)

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
