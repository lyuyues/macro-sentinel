import numpy as np
import pandas as pd
import pytest
from quant.strategy import generate_signals, check_sell_conditions


class TestGenerateSignals:
    def test_returns_dict_of_scores(self):
        scores = {"AAPL": 0.8, "GOOGL": 0.6, "MSFT": 0.3}
        trend_ok = {"AAPL": True, "GOOGL": True, "MSFT": False}
        result = generate_signals(scores, trend_ok, regime="offensive", n_universe=5)
        assert "MSFT" not in result
        assert "AAPL" in result

    def test_defensive_regime_fewer_picks(self):
        scores = {f"T{i}": 0.9 - i * 0.1 for i in range(10)}
        trend_ok = {f"T{i}": True for i in range(10)}
        result = generate_signals(scores, trend_ok, regime="defensive", n_universe=10)
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
