"""CLI entry point for Phase 3 analysis: single factor, sensitivity, combinations."""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.data_loader import load_price_data, load_vix, load_yield_spread
from quant.run_backtest import create_universe_function, START_DATE, END_DATE, INITIAL_CASH
from quant.analysis import (
    run_batch,
    compare_results,
    build_single_factor_configs,
    build_sensitivity_configs,
    build_2d_sensitivity_configs,
    build_combination_configs,
    plot_comparison_bar,
    plot_sensitivity_line,
    plot_sensitivity_heatmap,
    plot_nav_overlay,
    plot_ternary_scatter,
)

OUTPUT_BASE = "output/analysis"


def _load_shared_data():
    """Load prices, macro, and universe once for all analyses."""
    print("Running screener...")
    universe_func, universe, fair_values, rejected = create_universe_function()
    print(f"  Qualified: {len(universe)} stocks")

    print("Loading prices...")
    all_tickers = universe + ["SPY"]
    prices = load_price_data(all_tickers, start=START_DATE, end=END_DATE)
    valid_universe = [
        t for t in universe
        if t in prices.columns and prices[t].dropna().shape[0] > 252
    ]
    valid_fv = {t: fair_values[t] for t in valid_universe}

    def valid_universe_func(date):
        return valid_universe, valid_fv

    print("Loading macro data...")
    vix = load_vix(start=START_DATE, end=END_DATE)
    spread = load_yield_spread(start=START_DATE, end=END_DATE)

    print(f"  Universe: {len(valid_universe)} stocks, "
          f"price data: {prices.shape[0]} days")

    return {
        "prices": prices,
        "universe": valid_universe,
        "fair_values": valid_fv,
        "vix": vix,
        "yield_spread": spread,
        "universe_func": valid_universe_func,
    }


def _run_configs(configs, data, label=""):
    """Helper to run batch and print progress."""
    print(f"  Running {len(configs)} configs{' (' + label + ')' if label else ''}...")
    df, navs = run_batch(
        configs=configs,
        prices=data["prices"],
        universe=data["universe"],
        fair_values=data["fair_values"],
        benchmark="SPY",
        initial_cash=INITIAL_CASH,
        vix=data["vix"],
        yield_spread=data["yield_spread"],
        universe_func=data["universe_func"],
    )
    return compare_results(df), navs


def run_single_factor(data):
    """Task 3: Single factor analysis."""
    print("\n=== Single Factor Analysis ===")
    out_dir = os.path.join(OUTPUT_BASE, "single_factor")
    os.makedirs(out_dir, exist_ok=True)

    configs = build_single_factor_configs()
    df, navs = _run_configs(configs, data, "single_factor")

    # Save
    df.to_csv(os.path.join(out_dir, "comparison.csv"), index=False)
    plot_comparison_bar(df, "sharpe", os.path.join(out_dir, "sharpe_comparison.png"),
                        title="Sharpe Ratio: Single Factor Analysis")
    plot_nav_overlay(navs, os.path.join(out_dir, "nav_overlay.png"),
                     title="NAV: Single Factor Comparison")

    print(f"  Results saved to {out_dir}/")
    print(df[["label", "cagr", "sharpe", "max_drawdown", "alpha"]].to_string(index=False))


def run_sensitivity(data):
    """Task 4: Parameter sensitivity analysis."""
    print("\n=== Parameter Sensitivity Analysis ===")
    sweeps = build_sensitivity_configs()

    for param_name, configs in sweeps.items():
        out_dir = os.path.join(OUTPUT_BASE, "sensitivity", param_name)
        os.makedirs(out_dir, exist_ok=True)

        df, navs = _run_configs(configs, data, param_name)

        df.to_csv(os.path.join(out_dir, "comparison.csv"), index=False)
        plot_sensitivity_line(
            df, param_name, "sharpe",
            os.path.join(out_dir, "sharpe_vs_param.png"),
        )
        plot_sensitivity_line(
            df, param_name, "cagr",
            os.path.join(out_dir, "cagr_vs_param.png"),
        )
        plot_sensitivity_line(
            df, param_name, "max_drawdown",
            os.path.join(out_dir, "dd_vs_param.png"),
        )
        print(f"  {param_name}: saved to {out_dir}/")

    # 2D sweep: stop_loss x momentum_lookback
    print("  Running 2D sweep: stop_loss_pct x momentum_lookback...")
    out_dir_2d = os.path.join(OUTPUT_BASE, "sensitivity", "2d_sl_mom")
    os.makedirs(out_dir_2d, exist_ok=True)

    configs_2d = build_2d_sensitivity_configs()
    df_2d, _ = _run_configs(configs_2d, data, "2d_sweep")

    df_2d.to_csv(os.path.join(out_dir_2d, "comparison.csv"), index=False)
    plot_sensitivity_heatmap(
        df_2d, "stop_loss_pct", "momentum_lookback", "sharpe",
        os.path.join(out_dir_2d, "heatmap_sharpe.png"),
    )
    plot_sensitivity_heatmap(
        df_2d, "stop_loss_pct", "momentum_lookback", "cagr",
        os.path.join(out_dir_2d, "heatmap_cagr.png"),
    )
    print(f"  2D sweep saved to {out_dir_2d}/")


def run_combinations(data):
    """Task 5: Factor combination analysis."""
    print("\n=== Factor Combination Analysis ===")
    out_dir = os.path.join(OUTPUT_BASE, "combinations")
    os.makedirs(out_dir, exist_ok=True)

    configs = build_combination_configs(step=0.10)
    print(f"  {len(configs)} weight combinations to test")
    df, navs = _run_configs(configs, data, "combinations")

    df.to_csv(os.path.join(out_dir, "comparison.csv"), index=False)

    # Top 10 by Sharpe
    top10 = df.nlargest(10, "sharpe")
    with open(os.path.join(out_dir, "top_10.md"), "w") as f:
        f.write("# Top 10 Factor Combinations by Sharpe Ratio\n\n")
        f.write("| Rank | Label | Sharpe | CAGR | Max DD | Alpha |\n")
        f.write("|------|-------|--------|------|--------|-------|\n")
        for i, (_, row) in enumerate(top10.iterrows(), 1):
            f.write(
                f"| {i} | {row['label']} | {row['sharpe']:.3f} | "
                f"{row['cagr']:.1%} | {row['max_drawdown']:.1%} | "
                f"{row['alpha']:.2%} |\n"
            )

    plot_ternary_scatter(df, "sharpe", os.path.join(out_dir, "ternary_sharpe.png"))
    plot_ternary_scatter(df, "cagr", os.path.join(out_dir, "ternary_cagr.png"))

    # NAV overlay for top 5
    top5_labels = top10["label"].head(5).tolist()
    top5_navs = {k: v for k, v in navs.items() if k in top5_labels}
    if top5_navs:
        plot_nav_overlay(
            top5_navs,
            os.path.join(out_dir, "nav_top5.png"),
            title="NAV: Top 5 Factor Combinations",
        )

    print(f"  Results saved to {out_dir}/")
    print("  Top 5 by Sharpe:")
    print(top10[["label", "cagr", "sharpe", "max_drawdown", "alpha"]].head(5).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Phase 3: Factor analysis and parameter tuning")
    parser.add_argument(
        "--analysis",
        choices=["single_factor", "sensitivity", "combinations", "all"],
        default="all",
        help="Which analysis to run",
    )
    args = parser.parse_args()

    data = _load_shared_data()

    if args.analysis in ("single_factor", "all"):
        run_single_factor(data)
    if args.analysis in ("sensitivity", "all"):
        run_sensitivity(data)
    if args.analysis in ("combinations", "all"):
        run_combinations(data)

    print("\nDone.")


if __name__ == "__main__":
    main()
