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
