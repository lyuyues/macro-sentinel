"""MACD triple divergence reversal strategy (half-wood-summer style)."""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd


@dataclass
class MACDConfig:
    """Configuration for MACD triple divergence strategy."""

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    noise_threshold: float = 0.0  # abs(histogram) <= this is absorbed into current segment
    min_segment_bars: int = 2  # minimum bars for a valid segment
    max_holding_days: int = 30
    max_positions: int = 5
    confirm_next_bar: bool = True  # require next-bar histogram confirmation


@dataclass
class HistogramSegment:
    """A contiguous run of same-sign MACD histogram bars."""

    start_idx: int
    end_idx: int
    sign: int  # +1 or -1
    peak_value: float  # max for positive, min for negative
    peak_idx: int
    price_extreme: float  # max(highs) for positive, min(lows) for negative
    price_extreme_idx: int


@dataclass
class DivergenceSignal:
    """A detected triple divergence signal."""

    signal_type: str  # "bullish" or "bearish"
    bar_idx: int  # bar index where signal is detected
    segments: list = field(default_factory=list)  # 3 HistogramSegments
    price_extremes: list = field(default_factory=list)  # 3 price extreme values
    histogram_peaks: list = field(default_factory=list)  # 3 abs(peak) values
    stop_loss_price: float = 0.0


def compute_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD line, signal line, and histogram.

    Returns DataFrame with columns: macd_line, signal_line, histogram.
    """
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame(
        {"macd_line": macd_line, "signal_line": signal_line, "histogram": histogram},
        index=prices.index,
    )


def build_histogram_segments(
    histogram: np.ndarray,
    prices_high: np.ndarray,
    prices_low: np.ndarray,
    noise_threshold: float = 0.0,
    min_segment_bars: int = 2,
) -> List[HistogramSegment]:
    """Split histogram into contiguous same-sign segments.

    Bars with abs(h) <= noise_threshold are absorbed into the current segment.
    Segments shorter than min_segment_bars are discarded.
    """
    n = len(histogram)
    if n == 0:
        return []

    segments: List[HistogramSegment] = []
    current_sign = 0
    start = 0
    values: list = []
    indices: list = []

    def _flush(start_idx, indices, values, sign):
        if len(indices) < min_segment_bars:
            return
        arr = np.array(values)
        if sign == 1:
            peak_pos = int(np.argmax(arr))
            peak_val = float(arr[peak_pos])
            highs_slice = prices_high[indices]
            pe_pos = int(np.argmax(highs_slice))
            pe_val = float(highs_slice[pe_pos])
        else:
            peak_pos = int(np.argmin(arr))
            peak_val = float(arr[peak_pos])
            lows_slice = prices_low[indices]
            pe_pos = int(np.argmin(lows_slice))
            pe_val = float(lows_slice[pe_pos])

        segments.append(HistogramSegment(
            start_idx=indices[0],
            end_idx=indices[-1],
            sign=sign,
            peak_value=peak_val,
            peak_idx=indices[peak_pos],
            price_extreme=pe_val,
            price_extreme_idx=indices[pe_pos],
        ))

    for i in range(n):
        h = histogram[i]

        # Determine bar sign (noise bars keep current sign)
        if abs(h) <= noise_threshold:
            bar_sign = current_sign if current_sign != 0 else (1 if h >= 0 else -1)
        else:
            bar_sign = 1 if h > 0 else -1

        if current_sign == 0:
            # First bar
            current_sign = bar_sign
            start = i
            values = [h]
            indices = [i]
        elif bar_sign == current_sign:
            values.append(h)
            indices.append(i)
        else:
            # Sign flipped: flush current segment, start new one
            _flush(start, indices, values, current_sign)
            current_sign = bar_sign
            start = i
            values = [h]
            indices = [i]

    # Flush last segment
    if indices:
        _flush(start, indices, values, current_sign)

    return segments


def detect_triple_divergence(
    segments: List[HistogramSegment],
    current_idx: int,
) -> Optional[DivergenceSignal]:
    """Detect triple divergence from completed segments.

    Bullish (bottom) divergence: 3 negative segments with
      - prices making lower lows (decreasing price_extreme)
      - histogram amplitude diminishing (abs(peak) decreasing)
      - separated by positive segments in between

    Bearish (top) divergence: 3 positive segments with
      - prices making higher highs (increasing price_extreme)
      - histogram amplitude diminishing (abs(peak) decreasing)
      - separated by negative segments in between

    Returns bullish signal preferentially (long-only strategy).
    """
    # Try bullish divergence (negative segments)
    signal = _check_divergence(segments, current_idx, target_sign=-1, signal_type="bullish")
    if signal:
        return signal

    # Try bearish divergence (positive segments)
    return _check_divergence(segments, current_idx, target_sign=1, signal_type="bearish")


def _check_divergence(
    segments: List[HistogramSegment],
    current_idx: int,
    target_sign: int,
    signal_type: str,
) -> Optional[DivergenceSignal]:
    """Check for triple divergence in segments of the given sign."""
    # Collect recent segments of target sign
    target_segs = [s for s in segments if s.sign == target_sign and s.end_idx <= current_idx]
    if len(target_segs) < 3:
        return None

    # Take the most recent 3
    last3 = target_segs[-3:]

    # Verify they are separated by opposite-sign segments
    all_segs_between = [s for s in segments if s.sign == -target_sign]
    for i in range(2):
        gap_start = last3[i].end_idx
        gap_end = last3[i + 1].start_idx
        has_opposite = any(
            s.start_idx >= gap_start and s.end_idx <= gap_end
            for s in all_segs_between
        )
        if not has_opposite:
            return None

    peaks = [abs(s.peak_value) for s in last3]
    prices = [s.price_extreme for s in last3]

    # Histogram amplitude must be diminishing
    if not (peaks[0] > peaks[1] > peaks[2]):
        return None

    # Price trend must be present
    if signal_type == "bullish":
        # Lower lows in price
        if not (prices[0] > prices[1] > prices[2]):
            return None
        stop_loss = min(prices)
    else:
        # Higher highs in price
        if not (prices[0] < prices[1] < prices[2]):
            return None
        stop_loss = max(prices)

    return DivergenceSignal(
        signal_type=signal_type,
        bar_idx=current_idx,
        segments=list(last3),
        price_extremes=prices,
        histogram_peaks=peaks,
        stop_loss_price=stop_loss,
    )


def check_exit_signal(
    entry_price: float,
    stop_loss_price: float,
    entry_bar_idx: int,
    current_bar_idx: int,
    current_price: float,
    current_histogram: float,
    prev_histogram: float,
    bearish_signal: Optional[DivergenceSignal],
    config: MACDConfig,
) -> tuple:
    """Check if a long position should be exited.

    Priority: stop_loss > histogram_reversal (next-bar confirm fail)
              > reverse_divergence (bearish) > max_holding

    Returns (should_exit: bool, reason: str).
    """
    # 1. Stop loss
    if current_price <= stop_loss_price:
        return True, "stop_loss"

    holding_days = current_bar_idx - entry_bar_idx

    # 2. Next-bar histogram confirmation failure
    if config.confirm_next_bar and holding_days == 1:
        # On the day after entry, histogram should be growing (less negative / more positive)
        # i.e. current_histogram > prev_histogram for a bullish position
        if not np.isnan(current_histogram) and not np.isnan(prev_histogram):
            if current_histogram <= prev_histogram:
                return True, "histogram_reversal"

    # 3. Bearish divergence detected (top divergence as profit-taking)
    if bearish_signal is not None:
        return True, "reverse_divergence"

    # 4. Max holding days
    if holding_days >= config.max_holding_days:
        return True, "max_holding"

    return False, ""
