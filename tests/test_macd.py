import numpy as np
import pandas as pd
import pytest
from quant.macd_strategy import (
    MACDConfig,
    HistogramSegment,
    DivergenceSignal,
    compute_macd,
    build_histogram_segments,
    detect_triple_divergence,
    check_exit_signal,
)


class TestComputeMACD:
    def test_constant_price_zero_histogram(self):
        """Constant price should yield histogram ~ 0."""
        prices = pd.Series([100.0] * 60)
        result = compute_macd(prices)
        assert result["histogram"].iloc[-1] == pytest.approx(0.0, abs=1e-6)

    def test_uptrend_positive_macd(self):
        """Uptrending price should give positive MACD line."""
        prices = pd.Series(np.linspace(100, 200, 60))
        result = compute_macd(prices)
        assert result["macd_line"].iloc[-1] > 0

    def test_downtrend_negative_macd(self):
        """Downtrending price should give negative MACD line."""
        prices = pd.Series(np.linspace(200, 100, 60))
        result = compute_macd(prices)
        assert result["macd_line"].iloc[-1] < 0

    def test_output_shape(self):
        """Output should have same length as input with 3 columns."""
        prices = pd.Series(np.random.RandomState(42).normal(100, 5, 100))
        result = compute_macd(prices)
        assert result.shape == (100, 3)
        assert list(result.columns) == ["macd_line", "signal_line", "histogram"]

    def test_custom_periods(self):
        """Custom periods should not error."""
        prices = pd.Series(np.linspace(100, 150, 60))
        result = compute_macd(prices, fast=5, slow=10, signal=3)
        assert len(result) == 60


class TestSegmentDetection:
    def test_simple_alternating(self):
        """Alternating positive/negative runs should produce segments."""
        histogram = np.array([1, 2, 1, -1, -2, -1, 1, 2, 3, 1])
        highs = np.array([100, 101, 100, 99, 98, 99, 100, 101, 102, 101])
        lows = np.array([98, 99, 98, 97, 96, 97, 98, 99, 100, 99])
        segments = build_histogram_segments(histogram, highs, lows, min_segment_bars=2)
        assert len(segments) >= 2
        # First segment should be positive
        assert segments[0].sign == 1

    def test_noise_threshold_absorbs(self):
        """Small bars within noise_threshold should be absorbed into current segment."""
        # Positive run with a tiny negative bar in the middle
        histogram = np.array([1, 2, -0.05, 1, 2])
        highs = np.array([100, 101, 100, 101, 102])
        lows = np.array([98, 99, 98, 99, 100])
        segments = build_histogram_segments(
            histogram, highs, lows, noise_threshold=0.1, min_segment_bars=2
        )
        # Should be a single positive segment (the -0.05 is absorbed)
        assert len(segments) == 1
        assert segments[0].sign == 1
        assert segments[0].start_idx == 0
        assert segments[0].end_idx == 4

    def test_min_segment_bars_filter(self):
        """Segments shorter than min_segment_bars should be discarded."""
        histogram = np.array([1, -1, 2, 3, 4])
        highs = np.array([100, 99, 101, 102, 103])
        lows = np.array([98, 97, 99, 100, 101])
        segments = build_histogram_segments(
            histogram, highs, lows, min_segment_bars=2
        )
        # The single +1 bar and single -1 bar are discarded; only [2,3,4] segment remains
        assert len(segments) == 1
        assert segments[0].sign == 1

    def test_peak_tracking(self):
        """Segment should track the peak histogram value and price extreme."""
        histogram = np.array([-1, -3, -2, -1])
        highs = np.array([100, 98, 99, 100])
        lows = np.array([97, 94, 95, 96])
        segments = build_histogram_segments(histogram, highs, lows, min_segment_bars=2)
        assert len(segments) == 1
        seg = segments[0]
        assert seg.sign == -1
        assert seg.peak_value == -3.0  # min for negative
        assert seg.peak_idx == 1
        assert seg.price_extreme == 94.0  # min of lows
        assert seg.price_extreme_idx == 1

    def test_positive_segment_peak(self):
        """Positive segment should track max histogram and max high."""
        histogram = np.array([1, 4, 2])
        highs = np.array([100, 105, 103])
        lows = np.array([98, 100, 99])
        segments = build_histogram_segments(histogram, highs, lows, min_segment_bars=2)
        assert len(segments) == 1
        seg = segments[0]
        assert seg.sign == 1
        assert seg.peak_value == 4.0
        assert seg.price_extreme == 105.0

    def test_empty_histogram(self):
        """Empty input should return empty list."""
        segments = build_histogram_segments(
            np.array([]), np.array([]), np.array([])
        )
        assert segments == []


class TestTripleDivergence:
    def _make_bearish_segments(self):
        """Create segments showing bearish (top) divergence:
        3 positive segments with higher price highs but diminishing histogram peaks.
        Separated by negative segments.
        """
        return [
            HistogramSegment(0, 5, 1, 5.0, 3, 100.0, 3),
            HistogramSegment(6, 8, -1, -1.0, 7, 95.0, 7),
            HistogramSegment(9, 14, 1, 4.0, 12, 105.0, 12),
            HistogramSegment(15, 17, -1, -1.0, 16, 96.0, 16),
            HistogramSegment(18, 23, 1, 3.0, 21, 110.0, 21),
        ]

    def _make_bullish_segments(self):
        """Create segments showing bullish (bottom) divergence:
        3 negative segments with lower price lows but diminishing histogram magnitude.
        Separated by positive segments.
        """
        return [
            HistogramSegment(0, 5, -1, -5.0, 3, 100.0, 3),
            HistogramSegment(6, 8, 1, 1.0, 7, 105.0, 7),
            HistogramSegment(9, 14, -1, -4.0, 12, 95.0, 12),
            HistogramSegment(15, 17, 1, 1.0, 16, 106.0, 16),
            HistogramSegment(18, 23, -1, -3.0, 21, 90.0, 21),
        ]

    def test_bullish_divergence_detected(self):
        """Should detect bullish divergence with 3 negative segments."""
        segments = self._make_bullish_segments()
        signal = detect_triple_divergence(segments, current_idx=25)
        assert signal is not None
        assert signal.signal_type == "bullish"
        assert len(signal.segments) == 3
        # Histogram peaks should be diminishing
        assert signal.histogram_peaks[0] > signal.histogram_peaks[1] > signal.histogram_peaks[2]
        # Price extremes should be decreasing (lower lows)
        assert signal.price_extremes[0] > signal.price_extremes[1] > signal.price_extremes[2]

    def test_bearish_divergence_detected(self):
        """Should detect bearish divergence with 3 positive segments."""
        segments = self._make_bearish_segments()
        signal = detect_triple_divergence(segments, current_idx=25)
        # Bullish checked first; only bearish segments here, so no bullish
        assert signal is not None
        assert signal.signal_type == "bearish"

    def test_no_signal_histogram_not_diminishing(self):
        """If histogram peaks are not diminishing, no signal."""
        segments = [
            HistogramSegment(0, 5, -1, -3.0, 3, 100.0, 3),
            HistogramSegment(6, 8, 1, 1.0, 7, 105.0, 7),
            HistogramSegment(9, 14, -1, -4.0, 12, 95.0, 12),  # increasing!
            HistogramSegment(15, 17, 1, 1.0, 16, 106.0, 16),
            HistogramSegment(18, 23, -1, -5.0, 21, 90.0, 21),  # increasing!
        ]
        signal = detect_triple_divergence(segments, current_idx=25)
        assert signal is None

    def test_no_signal_price_not_trending(self):
        """If prices don't trend (no lower lows), no bullish signal."""
        segments = [
            HistogramSegment(0, 5, -1, -5.0, 3, 90.0, 3),
            HistogramSegment(6, 8, 1, 1.0, 7, 105.0, 7),
            HistogramSegment(9, 14, -1, -4.0, 12, 95.0, 12),  # higher low!
            HistogramSegment(15, 17, 1, 1.0, 16, 106.0, 16),
            HistogramSegment(18, 23, -1, -3.0, 21, 92.0, 21),  # higher low!
        ]
        signal = detect_triple_divergence(segments, current_idx=25)
        assert signal is None

    def test_insufficient_segments(self):
        """Fewer than 3 same-sign segments should give no signal."""
        segments = [
            HistogramSegment(0, 5, -1, -5.0, 3, 100.0, 3),
            HistogramSegment(6, 8, 1, 1.0, 7, 105.0, 7),
            HistogramSegment(9, 14, -1, -4.0, 12, 95.0, 12),
        ]
        signal = detect_triple_divergence(segments, current_idx=16)
        assert signal is None

    def test_bullish_stop_loss_is_lowest_price(self):
        """Bullish signal stop_loss should be the minimum of price_extremes."""
        segments = self._make_bullish_segments()
        signal = detect_triple_divergence(segments, current_idx=25)
        assert signal is not None
        assert signal.stop_loss_price == 90.0  # min of [100, 95, 90]


class TestCheckExitSignal:
    def test_stop_loss(self):
        """Should exit when price falls to stop loss."""
        config = MACDConfig()
        should_exit, reason = check_exit_signal(
            entry_price=100.0, stop_loss_price=90.0,
            entry_bar_idx=10, current_bar_idx=15,
            current_price=89.0, current_histogram=0.5, prev_histogram=0.3,
            bearish_signal=None, config=config,
        )
        assert should_exit is True
        assert reason == "stop_loss"

    def test_reverse_divergence(self):
        """Should exit on bearish divergence."""
        config = MACDConfig()
        bearish = DivergenceSignal(
            signal_type="bearish", bar_idx=20,
            segments=[], price_extremes=[], histogram_peaks=[],
            stop_loss_price=0.0,
        )
        should_exit, reason = check_exit_signal(
            entry_price=100.0, stop_loss_price=90.0,
            entry_bar_idx=10, current_bar_idx=20,
            current_price=110.0, current_histogram=0.5, prev_histogram=0.3,
            bearish_signal=bearish, config=config,
        )
        assert should_exit is True
        assert reason == "reverse_divergence"

    def test_max_holding(self):
        """Should exit after max holding days."""
        config = MACDConfig(max_holding_days=30)
        should_exit, reason = check_exit_signal(
            entry_price=100.0, stop_loss_price=90.0,
            entry_bar_idx=10, current_bar_idx=41,
            current_price=105.0, current_histogram=0.5, prev_histogram=0.3,
            bearish_signal=None, config=config,
        )
        assert should_exit is True
        assert reason == "max_holding"

    def test_histogram_reversal_on_day_1(self):
        """Should exit if next-bar histogram fails to confirm."""
        config = MACDConfig(confirm_next_bar=True)
        should_exit, reason = check_exit_signal(
            entry_price=100.0, stop_loss_price=90.0,
            entry_bar_idx=10, current_bar_idx=11,  # day 1 after entry
            current_price=101.0, current_histogram=-0.5, prev_histogram=-0.3,
            bearish_signal=None, config=config,
        )
        assert should_exit is True
        assert reason == "histogram_reversal"

    def test_no_exit(self):
        """Should not exit when all conditions are fine."""
        config = MACDConfig()
        should_exit, reason = check_exit_signal(
            entry_price=100.0, stop_loss_price=90.0,
            entry_bar_idx=10, current_bar_idx=15,
            current_price=102.0, current_histogram=0.5, prev_histogram=0.3,
            bearish_signal=None, config=config,
        )
        assert should_exit is False
        assert reason == ""

    def test_stop_loss_priority_over_all(self):
        """Stop loss should take priority over other exit reasons."""
        config = MACDConfig(max_holding_days=5)
        bearish = DivergenceSignal(
            signal_type="bearish", bar_idx=20,
            segments=[], price_extremes=[], histogram_peaks=[],
            stop_loss_price=0.0,
        )
        should_exit, reason = check_exit_signal(
            entry_price=100.0, stop_loss_price=90.0,
            entry_bar_idx=10, current_bar_idx=20,
            current_price=85.0, current_histogram=-1.0, prev_histogram=-0.5,
            bearish_signal=bearish, config=config,
        )
        assert should_exit is True
        assert reason == "stop_loss"

    def test_no_confirm_disables_histogram_reversal(self):
        """With confirm_next_bar=False, should not check histogram reversal."""
        config = MACDConfig(confirm_next_bar=False)
        should_exit, reason = check_exit_signal(
            entry_price=100.0, stop_loss_price=90.0,
            entry_bar_idx=10, current_bar_idx=11,
            current_price=101.0, current_histogram=-0.5, prev_histogram=-0.3,
            bearish_signal=None, config=config,
        )
        assert should_exit is False
        assert reason == ""


class TestMACDBacktester:
    def _make_ohlc(self, n_days=200, seed=42):
        """Create synthetic OHLC data with divergence-like patterns."""
        dates = pd.bdate_range("2020-01-01", periods=n_days)
        rng = np.random.RandomState(seed)

        close = 100.0 + np.cumsum(rng.normal(0.05, 1.0, n_days))
        high = close + rng.uniform(0.5, 2.0, n_days)
        low = close - rng.uniform(0.5, 2.0, n_days)

        close_b = 50.0 + np.cumsum(rng.normal(0.02, 0.8, n_days))
        high_b = close_b + rng.uniform(0.3, 1.5, n_days)
        low_b = close_b - rng.uniform(0.3, 1.5, n_days)

        spy_close = 400.0 + np.cumsum(rng.normal(0.05, 0.5, n_days))

        prices = pd.DataFrame({"AAA": close, "BBB": close_b, "SPY": spy_close}, index=dates)
        prices_high = pd.DataFrame({"AAA": high, "BBB": high_b, "SPY": spy_close + 1}, index=dates)
        prices_low = pd.DataFrame({"AAA": low, "BBB": low_b, "SPY": spy_close - 1}, index=dates)

        return prices, prices_high, prices_low

    def test_smoke(self):
        """Backtester runs without error on synthetic data."""
        from quant.macd_backtest import MACDBacktester

        prices, prices_high, prices_low = self._make_ohlc()
        config = MACDConfig(max_positions=2)
        bt = MACDBacktester(
            prices=prices, prices_high=prices_high, prices_low=prices_low,
            universe=["AAA", "BBB"], config=config, benchmark="SPY",
        )
        result = bt.run()
        assert "nav" in result
        assert "trades" in result
        assert "metrics" in result
        assert len(result["nav"]) == len(prices)
        assert result["nav"].iloc[0] == pytest.approx(100_000.0)

    def test_max_positions_respected(self):
        """Should not exceed max_positions."""
        from quant.macd_backtest import MACDBacktester

        prices, prices_high, prices_low = self._make_ohlc()
        config = MACDConfig(max_positions=1)
        bt = MACDBacktester(
            prices=prices, prices_high=prices_high, prices_low=prices_low,
            universe=["AAA", "BBB"], config=config, benchmark="SPY",
        )
        result = bt.run()
        for count in result["positions_over_time"]:
            assert count <= 1, f"Positions exceeded max: {count}"

    def test_nav_positive(self):
        """NAV should always be positive (no negative portfolio values)."""
        from quant.macd_backtest import MACDBacktester

        prices, prices_high, prices_low = self._make_ohlc()
        config = MACDConfig(max_positions=3)
        bt = MACDBacktester(
            prices=prices, prices_high=prices_high, prices_low=prices_low,
            universe=["AAA", "BBB"], config=config, benchmark="SPY",
        )
        result = bt.run()
        assert (result["nav"] > 0).all()
