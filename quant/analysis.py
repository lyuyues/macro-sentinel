"""Batch analysis engine: run_batch, config builders, plotting."""
from __future__ import annotations
import os
import itertools
from copy import deepcopy

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from quant.config import BacktestConfig
from quant.backtest import Backtester


# ------------------------------------------------------------------
# Core: batch runner + comparison
# ------------------------------------------------------------------

def run_batch(
    configs: list[BacktestConfig],
    prices: pd.DataFrame,
    universe: list,
    fair_values: dict,
    benchmark: str = "SPY",
    initial_cash: float = 100_000.0,
    vix: pd.Series = None,
    yield_spread: pd.Series = None,
    universe_func: callable = None,
) -> tuple[pd.DataFrame, dict]:
    """Run multiple configs through Backtester, return (metrics_df, nav_dict).

    Returns:
        metrics_df: DataFrame with one row per config, metrics as columns.
        nav_dict: {label: nav_series} for NAV overlay plots.
    """
    rows = []
    nav_dict = {}

    for cfg in configs:
        bt = Backtester(
            prices=prices,
            universe=universe,
            fair_values=fair_values,
            benchmark=benchmark,
            initial_cash=initial_cash,
            vix=vix,
            yield_spread=yield_spread,
            universe_func=universe_func,
            config=cfg,
        )
        result = bt.run()
        row = {"label": cfg.label}
        row.update(result["metrics"])
        # Store config params for sensitivity analysis
        row["stop_loss_pct"] = cfg.stop_loss_pct
        row["max_position_weight"] = cfg.max_position_weight
        row["momentum_lookback"] = cfg.momentum_lookback
        row["sma_window"] = cfg.sma_window
        if cfg.factor_weights:
            row["w_value"] = cfg.factor_weights.get("value", 0)
            row["w_momentum"] = cfg.factor_weights.get("momentum", 0)
            row["w_cycle"] = cfg.factor_weights.get("cycle", 0)
        rows.append(row)
        nav_dict[cfg.label] = result["nav"]

    df = pd.DataFrame(rows)
    return df, nav_dict


def compare_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """Add rank columns for key metrics."""
    df = results_df.copy()
    for metric in ["sharpe", "cagr", "max_drawdown", "sortino", "calmar", "alpha"]:
        if metric in df.columns:
            ascending = metric == "max_drawdown"  # lower DD is better
            df[f"{metric}_rank"] = df[metric].rank(ascending=ascending).astype(int)
    return df


# ------------------------------------------------------------------
# Config builders
# ------------------------------------------------------------------

def build_single_factor_configs() -> list[BacktestConfig]:
    """7 configs testing factor contribution."""
    configs = [
        BacktestConfig(label="baseline"),  # regime defaults
        BacktestConfig(
            factor_weights={"value": 1.0, "momentum": 0.0, "cycle": 0.0},
            label="value_only",
        ),
        BacktestConfig(
            factor_weights={"value": 0.0, "momentum": 1.0, "cycle": 0.0},
            label="momentum_only",
        ),
        BacktestConfig(
            factor_weights={"value": 0.0, "momentum": 0.0, "cycle": 1.0},
            label="cycle_only",
        ),
        BacktestConfig(
            factor_weights={"value": 0.5, "momentum": 0.5, "cycle": 0.0},
            label="value_momentum",
        ),
        BacktestConfig(
            factor_weights={"value": 0.5, "momentum": 0.0, "cycle": 0.5},
            label="value_cycle",
        ),
        BacktestConfig(
            factor_weights={"value": 0.0, "momentum": 0.5, "cycle": 0.5},
            label="momentum_cycle",
        ),
    ]
    return configs


def build_sensitivity_configs() -> dict[str, list[BacktestConfig]]:
    """Parameter sweeps, keyed by parameter name."""
    sweeps = {}

    # Stop loss
    sweeps["stop_loss_pct"] = [
        BacktestConfig(stop_loss_pct=v, label=f"sl_{v:.2f}")
        for v in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.50]
    ]

    # Max position weight
    sweeps["max_position_weight"] = [
        BacktestConfig(max_position_weight=v, label=f"mw_{v:.2f}")
        for v in [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    ]

    # Momentum lookback
    sweeps["momentum_lookback"] = [
        BacktestConfig(momentum_lookback=v, label=f"mom_{v}")
        for v in [21, 42, 63, 126, 189, 252]
    ]

    # SMA window
    sweeps["sma_window"] = [
        BacktestConfig(sma_window=v, label=f"sma_{v}")
        for v in [50, 100, 150, 200, 250]
    ]

    return sweeps


def build_2d_sensitivity_configs() -> list[BacktestConfig]:
    """2D sweep: stop_loss_pct x momentum_lookback."""
    sl_vals = [0.05, 0.10, 0.15, 0.20, 0.25]
    mom_vals = [21, 63, 126, 189, 252]
    configs = []
    for sl, mom in itertools.product(sl_vals, mom_vals):
        configs.append(
            BacktestConfig(
                stop_loss_pct=sl,
                momentum_lookback=mom,
                label=f"sl{sl:.2f}_mom{mom}",
            )
        )
    return configs


def build_combination_configs(step: float = 0.10) -> list[BacktestConfig]:
    """All value+momentum+cycle=1.0 combinations at given step size."""
    configs = []
    steps = np.arange(0, 1.0 + step / 2, step)
    for v in steps:
        for m in steps:
            c = round(1.0 - v - m, 2)
            if c < -0.001 or c > 1.001:
                continue
            c = max(0.0, c)
            configs.append(
                BacktestConfig(
                    factor_weights={
                        "value": round(v, 2),
                        "momentum": round(m, 2),
                        "cycle": round(c, 2),
                    },
                    label=f"v{v:.0%}_m{m:.0%}_c{c:.0%}",
                )
            )
    return configs


# ------------------------------------------------------------------
# Plotting
# ------------------------------------------------------------------

def plot_comparison_bar(
    results_df: pd.DataFrame,
    metric: str,
    output_path: str,
    title: str = None,
):
    """Bar chart comparing a single metric across configs."""
    fig, ax = plt.subplots(figsize=(max(8, len(results_df) * 0.6), 5))
    bars = ax.bar(results_df["label"], results_df[metric])
    ax.set_title(title or f"{metric} Comparison")
    ax.set_ylabel(metric)
    plt.xticks(rotation=45, ha="right")

    # Annotate bars
    for bar, val in zip(bars, results_df[metric]):
        ax.annotate(
            f"{val:.3f}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            ha="center", va="bottom", fontsize=8,
        )

    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_sensitivity_line(
    results_df: pd.DataFrame,
    param: str,
    metric: str,
    output_path: str,
):
    """Line chart: parameter value vs metric."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(results_df[param], results_df[metric], "o-", linewidth=1.5)
    ax.set_xlabel(param)
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} vs {param}")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_sensitivity_heatmap(
    results_df: pd.DataFrame,
    param_x: str,
    param_y: str,
    metric: str,
    output_path: str,
):
    """2D heatmap of metric over two parameter axes."""
    pivot = results_df.pivot_table(
        index=param_y, columns=param_x, values=metric, aggfunc="first"
    )
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{v:.2f}" if isinstance(v, float) else str(v) for v in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(v) for v in pivot.index])
    ax.set_xlabel(param_x)
    ax.set_ylabel(param_y)
    ax.set_title(f"{metric}: {param_x} vs {param_y}")
    plt.colorbar(im, ax=ax)

    # Annotate cells
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if np.isfinite(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7)

    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_nav_overlay(nav_dict: dict, output_path: str, title: str = "NAV Comparison"):
    """Overlay multiple NAV curves."""
    fig, ax = plt.subplots(figsize=(12, 6))
    for label, nav in nav_dict.items():
        ax.plot(nav.index, nav.values, label=label, linewidth=1.0, alpha=0.8)
    ax.set_title(title)
    ax.set_ylabel("Portfolio Value ($)")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_ternary_scatter(
    results_df: pd.DataFrame,
    metric: str,
    output_path: str,
):
    """Scatter plot of factor combinations colored by metric (2D projection)."""
    if "w_value" not in results_df.columns:
        return
    fig, ax = plt.subplots(figsize=(8, 7))
    sc = ax.scatter(
        results_df["w_value"],
        results_df["w_momentum"],
        c=results_df[metric],
        cmap="RdYlGn",
        s=60,
        edgecolors="k",
        linewidth=0.3,
    )
    ax.set_xlabel("Value weight")
    ax.set_ylabel("Momentum weight")
    ax.set_title(f"{metric} by Factor Weights (cycle = 1 - value - momentum)")
    plt.colorbar(sc, ax=ax, label=metric)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
