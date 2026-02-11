"""Tests for analysis module: config builders, run_batch, plotting."""
import os
import pytest
import numpy as np
import pandas as pd

from quant.config import BacktestConfig
from quant.analysis import (
    run_batch,
    compare_results,
    build_single_factor_configs,
    build_sensitivity_configs,
    build_2d_sensitivity_configs,
    build_combination_configs,
    plot_comparison_bar,
    plot_nav_overlay,
)


@pytest.fixture
def synthetic_data():
    dates = pd.bdate_range("2023-01-01", "2024-12-31")
    np.random.seed(42)
    prices = pd.DataFrame({
        "AAA": 100 * np.cumprod(1 + np.random.normal(0.0003, 0.02, len(dates))),
        "BBB": 50 * np.cumprod(1 + np.random.normal(0.0002, 0.015, len(dates))),
        "CCC": 200 * np.cumprod(1 + np.random.normal(0.0001, 0.025, len(dates))),
        "SPY": 400 * np.cumprod(1 + np.random.normal(0.0003, 0.01, len(dates))),
    }, index=dates)
    fair_values = {"AAA": 120.0, "BBB": 45.0, "CCC": 250.0}
    universe = ["AAA", "BBB", "CCC"]
    return prices, universe, fair_values


class TestRunBatch:
    def test_returns_correct_shape(self, synthetic_data):
        """run_batch with 2 configs should return 2-row DataFrame."""
        prices, universe, fv = synthetic_data
        configs = [
            BacktestConfig(label="a"),
            BacktestConfig(stop_loss_pct=0.10, label="b"),
        ]
        df, navs = run_batch(configs, prices, universe, fv)
        assert len(df) == 2
        assert "label" in df.columns
        assert "sharpe" in df.columns
        assert len(navs) == 2
        assert "a" in navs and "b" in navs

    def test_nav_dict_has_series(self, synthetic_data):
        prices, universe, fv = synthetic_data
        configs = [BacktestConfig(label="test")]
        _, navs = run_batch(configs, prices, universe, fv)
        assert isinstance(navs["test"], pd.Series)
        assert len(navs["test"]) > 0


class TestCompareResults:
    def test_adds_rank_columns(self, synthetic_data):
        prices, universe, fv = synthetic_data
        configs = [
            BacktestConfig(label="x"),
            BacktestConfig(stop_loss_pct=0.05, label="y"),
            BacktestConfig(stop_loss_pct=0.30, label="z"),
        ]
        df, _ = run_batch(configs, prices, universe, fv)
        ranked = compare_results(df)
        assert "sharpe_rank" in ranked.columns
        assert "cagr_rank" in ranked.columns
        assert ranked["sharpe_rank"].max() == 3


class TestSingleFactorConfigs:
    def test_builds_7_configs(self):
        configs = build_single_factor_configs()
        assert len(configs) == 7

    def test_weights_sum_to_one(self):
        configs = build_single_factor_configs()
        for cfg in configs:
            if cfg.factor_weights is not None:
                total = sum(cfg.factor_weights.values())
                assert total == pytest.approx(1.0, abs=0.01), \
                    f"{cfg.label}: weights sum to {total}"

    def test_baseline_has_no_custom_weights(self):
        configs = build_single_factor_configs()
        baseline = [c for c in configs if c.label == "baseline"][0]
        assert baseline.factor_weights is None


class TestSensitivityConfigs:
    def test_all_param_sweeps_present(self):
        sweeps = build_sensitivity_configs()
        assert "stop_loss_pct" in sweeps
        assert "max_position_weight" in sweeps
        assert "momentum_lookback" in sweeps
        assert "sma_window" in sweeps

    def test_stop_loss_sweep_count(self):
        sweeps = build_sensitivity_configs()
        assert len(sweeps["stop_loss_pct"]) == 7

    def test_2d_sweep_count(self):
        configs = build_2d_sensitivity_configs()
        assert len(configs) == 25  # 5 x 5


class TestCombinationConfigs:
    def test_step_010_generates_66(self):
        configs = build_combination_configs(step=0.10)
        assert len(configs) == 66

    def test_step_020_generates_21(self):
        configs = build_combination_configs(step=0.20)
        assert len(configs) == 21

    def test_all_weights_sum_to_one(self):
        configs = build_combination_configs(step=0.10)
        for cfg in configs:
            total = sum(cfg.factor_weights.values())
            assert total == pytest.approx(1.0, abs=0.01), \
                f"{cfg.label}: weights sum to {total}"

    def test_no_negative_weights(self):
        configs = build_combination_configs(step=0.10)
        for cfg in configs:
            for k, v in cfg.factor_weights.items():
                assert v >= 0, f"{cfg.label}: {k}={v} is negative"


class TestPlotting:
    def test_bar_chart_creates_file(self, synthetic_data, tmp_path):
        prices, universe, fv = synthetic_data
        configs = [
            BacktestConfig(label="a"),
            BacktestConfig(label="b"),
        ]
        df, _ = run_batch(configs, prices, universe, fv)
        out = str(tmp_path / "bar.png")
        plot_comparison_bar(df, "sharpe", out)
        assert os.path.exists(out)

    def test_nav_overlay_creates_file(self, synthetic_data, tmp_path):
        prices, universe, fv = synthetic_data
        configs = [
            BacktestConfig(label="a"),
            BacktestConfig(label="b"),
        ]
        _, navs = run_batch(configs, prices, universe, fv)
        out = str(tmp_path / "nav.png")
        plot_nav_overlay(navs, out)
        assert os.path.exists(out)
