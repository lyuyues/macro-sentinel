import numpy as np
import pandas as pd
import pytest
from quant.bnf_strategy import BNFConfig, compute_ma_deviation, check_entry_signal, check_exit_signal


class TestComputeMADeviation:
    def test_basic_deviation(self):
        """Deviation should be 0 when price equals SMA."""
        prices = pd.Series([100.0] * 30)
        dev = compute_ma_deviation(prices, window=25)
        # After window, deviation should be ~0
        assert dev.iloc[-1] == pytest.approx(0.0, abs=1e-10)

    def test_positive_deviation(self):
        """Price above SMA should give positive deviation."""
        prices = pd.Series([100.0] * 25 + [120.0])
        dev = compute_ma_deviation(prices, window=25)
        # SMA25 at last point is close to 100 (slightly above due to 120)
        assert dev.iloc[-1] > 0

    def test_negative_deviation(self):
        """Price below SMA should give negative deviation."""
        prices = pd.Series([100.0] * 25 + [80.0])
        dev = compute_ma_deviation(prices, window=25)
        assert dev.iloc[-1] < 0

    def test_nan_before_window(self):
        """Deviation should be NaN before window period."""
        prices = pd.Series([100.0] * 30)
        dev = compute_ma_deviation(prices, window=25)
        assert np.isnan(dev.iloc[0])
        assert np.isnan(dev.iloc[23])
        assert not np.isnan(dev.iloc[24])

    def test_known_value(self):
        """Test with a known computed value."""
        # 25 days of 100, then price = 90
        prices = pd.Series([100.0] * 25 + [90.0])
        dev = compute_ma_deviation(prices, window=25)
        # SMA at index 25 = (100*24 + 90) / 25 = 99.6
        expected_sma = (100.0 * 24 + 90.0) / 25.0
        expected_dev = (90.0 - expected_sma) / expected_sma * 100.0
        assert dev.iloc[-1] == pytest.approx(expected_dev, rel=1e-6)


class TestCheckEntrySignal:
    def test_below_threshold_triggers(self):
        config = BNFConfig(entry_threshold=-10.0)
        assert check_entry_signal(-11.0, config) is True
        assert check_entry_signal(-15.0, config) is True

    def test_above_threshold_no_trigger(self):
        config = BNFConfig(entry_threshold=-10.0)
        assert check_entry_signal(-9.0, config) is False
        assert check_entry_signal(0.0, config) is False
        assert check_entry_signal(5.0, config) is False

    def test_at_threshold_no_trigger(self):
        config = BNFConfig(entry_threshold=-10.0)
        assert check_entry_signal(-10.0, config) is False

    def test_nan_no_trigger(self):
        config = BNFConfig()
        assert check_entry_signal(float("nan"), config) is False


class TestCheckExitSignal:
    def test_mean_reversion(self):
        config = BNFConfig(exit_threshold=0.0)
        should_exit, reason = check_exit_signal(
            current_deviation=0.5, entry_price=90.0, current_price=100.0,
            holding_days=5, config=config,
        )
        assert should_exit is True
        assert reason == "mean_reversion"

    def test_stop_loss(self):
        config = BNFConfig(stop_loss_pct=0.08)
        # Price dropped 10% from entry (beyond 8% stop)
        should_exit, reason = check_exit_signal(
            current_deviation=-15.0, entry_price=100.0, current_price=91.0,
            holding_days=3, config=config,
        )
        assert should_exit is True
        assert reason == "stop_loss"

    def test_max_holding(self):
        config = BNFConfig(max_holding_days=20)
        should_exit, reason = check_exit_signal(
            current_deviation=-5.0, entry_price=100.0, current_price=98.0,
            holding_days=20, config=config,
        )
        assert should_exit is True
        assert reason == "max_holding"

    def test_no_exit(self):
        config = BNFConfig()
        should_exit, reason = check_exit_signal(
            current_deviation=-3.0, entry_price=100.0, current_price=97.0,
            holding_days=5, config=config,
        )
        assert should_exit is False
        assert reason == ""

    def test_stop_loss_takes_priority_over_max_holding(self):
        """Stop loss should trigger before max holding check."""
        config = BNFConfig(stop_loss_pct=0.08, max_holding_days=20)
        should_exit, reason = check_exit_signal(
            current_deviation=-20.0, entry_price=100.0, current_price=85.0,
            holding_days=25, config=config,
        )
        assert should_exit is True
        assert reason == "stop_loss"


class TestBNFBacktester:
    def _make_prices(self, n_days=100, seed=42):
        """Create synthetic price data with a dip for testing."""
        dates = pd.bdate_range("2023-01-01", periods=n_days)
        np.random.seed(seed)
        # Create a stock that dips then recovers
        base = np.ones(n_days) * 100.0
        # Dip starting at day 40 for 10 days, then recover
        base[40:50] = np.linspace(100, 85, 10)
        base[50:60] = np.linspace(85, 100, 10)
        noise = np.random.normal(0, 0.5, n_days)
        stock_a = base + noise

        # Steady stock
        stock_b = 50 + np.cumsum(np.random.normal(0.01, 0.3, n_days))

        spy = 400 + np.cumsum(np.random.normal(0.05, 0.5, n_days))

        return pd.DataFrame(
            {"AAA": stock_a, "BBB": stock_b, "SPY": spy},
            index=dates,
        )

    def test_smoke(self):
        """Backtester runs without error on synthetic data."""
        from quant.bnf_backtest import BNFBacktester

        prices = self._make_prices(n_days=200)
        config = BNFConfig(entry_threshold=-10.0, max_positions=2)
        bt = BNFBacktester(
            prices=prices, universe=["AAA", "BBB"], config=config,
            benchmark="SPY",
        )
        result = bt.run()
        assert "nav" in result
        assert "trades" in result
        assert "metrics" in result
        assert len(result["nav"]) == len(prices)
        assert result["nav"].iloc[0] == pytest.approx(100_000.0)

    def test_buys_on_drop(self):
        """Should buy when deviation drops below threshold."""
        from quant.bnf_backtest import BNFBacktester

        dates = pd.bdate_range("2023-01-01", periods=80)
        # Create a stock with a clear drop at day 30
        stock = np.array([100.0] * 30 + [85.0] * 20 + [100.0] * 30)
        spy = np.array([400.0] * 80)
        prices = pd.DataFrame(
            {"AAA": stock, "SPY": spy},
            index=dates,
        )
        config = BNFConfig(
            ma_window=25, entry_threshold=-10.0, max_positions=5,
        )
        bt = BNFBacktester(prices=prices, universe=["AAA"], config=config)
        result = bt.run()
        trades = result["trades"]
        buy_trades = [t for t in trades if t["action"] == "buy"]
        assert len(buy_trades) > 0, "Should have at least one buy trade"

    def test_sells_on_reversion(self):
        """Should sell when price reverts to mean."""
        from quant.bnf_backtest import BNFBacktester

        dates = pd.bdate_range("2023-01-01", periods=100)
        # Stock: flat 100, drops to 85, then recovers to 100+
        stock = np.array(
            [100.0] * 30 + [85.0] * 10 + list(np.linspace(85, 105, 30)) + [105.0] * 30
        )
        spy = np.array([400.0] * 100)
        prices = pd.DataFrame(
            {"AAA": stock, "SPY": spy},
            index=dates,
        )
        config = BNFConfig(
            ma_window=25, entry_threshold=-10.0, exit_threshold=0.0,
            max_positions=5,
        )
        bt = BNFBacktester(prices=prices, universe=["AAA"], config=config)
        result = bt.run()
        trades = result["trades"]
        sell_trades = [t for t in trades if t["action"] == "sell"]
        if len([t for t in trades if t["action"] == "buy"]) > 0:
            assert len(sell_trades) > 0, "Should sell after price reverts"

    def test_max_positions_respected(self):
        """Should not exceed max_positions."""
        from quant.bnf_backtest import BNFBacktester

        dates = pd.bdate_range("2023-01-01", periods=80)
        # All stocks drop simultaneously
        base = np.array([100.0] * 30 + [80.0] * 50)
        prices = pd.DataFrame(
            {
                "A": base + np.random.RandomState(1).normal(0, 0.1, 80),
                "B": base + np.random.RandomState(2).normal(0, 0.1, 80),
                "C": base + np.random.RandomState(3).normal(0, 0.1, 80),
                "D": base + np.random.RandomState(4).normal(0, 0.1, 80),
                "SPY": np.array([400.0] * 80),
            },
            index=dates,
        )
        config = BNFConfig(
            ma_window=25, entry_threshold=-10.0, max_positions=2,
        )
        bt = BNFBacktester(
            prices=prices, universe=["A", "B", "C", "D"], config=config,
        )
        result = bt.run()
        # Check that positions never exceeded max
        for count in result["positions_over_time"]:
            assert count <= 2, f"Positions exceeded max: {count}"
