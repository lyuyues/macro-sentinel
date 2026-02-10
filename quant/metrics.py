"""Performance metrics for backtesting."""
import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def total_return(nav: pd.Series) -> float:
    """Total return from first to last NAV value."""
    return nav.iloc[-1] / nav.iloc[0] - 1.0


def cagr(nav: pd.Series) -> float:
    """Compound annual growth rate."""
    n_days = (nav.index[-1] - nav.index[0]).days
    if n_days <= 0:
        return 0.0
    years = n_days / 365.25
    return (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0


def max_drawdown(nav: pd.Series) -> float:
    """Maximum peak-to-trough drawdown (returned as positive number)."""
    peak = nav.cummax()
    dd = (peak - nav) / peak
    return float(dd.max())


def annualized_volatility(nav: pd.Series) -> float:
    """Annualized volatility of daily returns."""
    returns = nav.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    return float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def sharpe_ratio(nav: pd.Series, risk_free_rate: float = 0.04) -> float:
    """Annualized Sharpe ratio."""
    vol = annualized_volatility(nav)
    if vol == 0:
        return np.nan
    annual_ret = cagr(nav)
    return (annual_ret - risk_free_rate) / vol


def sortino_ratio(nav: pd.Series, risk_free_rate: float = 0.04) -> float:
    """Annualized Sortino ratio (only penalizes downside volatility)."""
    returns = nav.pct_change().dropna()
    downside = returns[returns < 0]
    if len(downside) == 0:
        return np.inf
    downside_std = float(downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    if downside_std == 0:
        return np.inf
    annual_ret = cagr(nav)
    return (annual_ret - risk_free_rate) / downside_std


def calmar_ratio(nav: pd.Series) -> float:
    """Calmar ratio = CAGR / Max Drawdown."""
    mdd = max_drawdown(nav)
    if mdd == 0:
        return np.nan
    return cagr(nav) / mdd


def compute_alpha_beta(
    strategy_nav: pd.Series, benchmark_nav: pd.Series
) -> tuple:
    """Compute alpha and beta vs benchmark using OLS on daily returns."""
    s_ret = strategy_nav.pct_change().dropna()
    b_ret = benchmark_nav.pct_change().dropna()
    # Align on common dates
    common = s_ret.index.intersection(b_ret.index)
    s_ret = s_ret.loc[common]
    b_ret = b_ret.loc[common]
    if len(common) < 2:
        return np.nan, np.nan
    # OLS: s = alpha + beta * b
    cov = np.cov(s_ret, b_ret)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else np.nan
    alpha = float(s_ret.mean() - beta * b_ret.mean()) * TRADING_DAYS_PER_YEAR
    return alpha, beta
