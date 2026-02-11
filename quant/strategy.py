"""Buy/sell signal generation and rebalancing rules."""
from quant.factors import REGIME_TOP_PCT


def generate_signals(
    composite_scores: dict,
    trend_confirmed: dict,
    regime: str,
    n_universe: int,
) -> dict:
    """Select stocks to buy based on composite score + trend filter.

    Returns {ticker: score} for stocks that pass all filters.
    """
    top_pct = REGIME_TOP_PCT.get(regime, 0.25)
    n_select = max(1, int(n_universe * top_pct))

    # Filter: must pass trend confirmation (F3)
    candidates = {
        t: s for t, s in composite_scores.items()
        if trend_confirmed.get(t, False)
    }

    # Sort by score descending, take top N
    sorted_tickers = sorted(candidates, key=candidates.get, reverse=True)
    selected = sorted_tickers[:n_select]

    return {t: candidates[t] for t in selected}


def check_sell_conditions(
    entry_price: float,
    current_price: float,
    fair_value: float,
    in_top_n: bool,
    trend_confirmed: bool,
    stop_loss_pct: float = 0.15,
) -> tuple:
    """Check if a position should be sold.

    Returns (should_sell, reason).
    """
    # 1. Stop loss
    loss = (entry_price - current_price) / entry_price
    if loss >= stop_loss_pct:
        return True, "stop_loss"

    # 2. Valuation recovery: price >= fair value
    if current_price >= fair_value and fair_value > 0:
        return True, "valuation_recovery"

    # 3. Score dropped out of top N
    if not in_top_n:
        return True, "score_dropped"

    # 4. Technical deterioration
    if not trend_confirmed:
        return True, "technical_deterioration"

    return False, "hold"
