import numpy as np
import pandas as pd
import pytest
from quant.portfolio import (
    compute_risk_parity_weights,
    apply_position_limits,
    calculate_trades,
)


class TestRiskParityWeights:
    def test_equal_vol(self):
        vols = {"AAPL": 0.20, "GOOGL": 0.20}
        weights = compute_risk_parity_weights(vols)
        assert weights["AAPL"] == pytest.approx(0.5)
        assert weights["GOOGL"] == pytest.approx(0.5)

    def test_different_vol(self):
        vols = {"AAPL": 0.10, "GOOGL": 0.30}
        weights = compute_risk_parity_weights(vols)
        assert weights["AAPL"] > weights["GOOGL"]
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_single_stock(self):
        vols = {"AAPL": 0.25}
        weights = compute_risk_parity_weights(vols)
        assert weights["AAPL"] == pytest.approx(1.0)


class TestPositionLimits:
    def test_cap_at_max(self):
        # 6 stocks: max 20% each = 120% capacity (feasible)
        weights = {"A": 0.40, "B": 0.25, "C": 0.15, "D": 0.10, "E": 0.05, "F": 0.05}
        capped = apply_position_limits(weights, max_weight=0.20)
        for w in capped.values():
            assert w <= 0.20 + 1e-9
        assert sum(capped.values()) == pytest.approx(1.0)

    def test_no_change_when_under_limit(self):
        weights = {"A": 0.15, "B": 0.15, "C": 0.15, "D": 0.15, "E": 0.15, "F": 0.25}
        capped = apply_position_limits(weights, max_weight=0.25)
        assert sum(capped.values()) == pytest.approx(1.0)


class TestCalculateTrades:
    def test_buy_from_cash(self):
        current = {}
        target = {"AAPL": 0.5, "GOOGL": 0.5}
        prices = {"AAPL": 200.0, "GOOGL": 150.0}
        cash = 100000.0
        trades = calculate_trades(current, target, prices, cash, max_exposure=1.0)
        assert trades["AAPL"]["action"] == "buy"
        assert trades["AAPL"]["dollars"] > 0

    def test_sell_removed_stock(self):
        current = {"AAPL": {"shares": 100, "value": 20000}}
        target = {}
        prices = {"AAPL": 200.0}
        trades = calculate_trades(current, target, prices, cash=0, max_exposure=1.0)
        assert trades["AAPL"]["action"] == "sell"
