"""Portfolio construction and risk parity weighting."""
import numpy as np

# Transaction costs
COMMISSION_RATE = 0.001   # 0.1% per side
SLIPPAGE_RATE = 0.0005    # 0.05% per side
COST_PER_SIDE = COMMISSION_RATE + SLIPPAGE_RATE  # 0.15%


def compute_risk_parity_weights(volatilities: dict) -> dict:
    """Risk parity: weight proportional to 1/volatility.

    Args:
        volatilities: {ticker: annualized_vol}

    Returns:
        {ticker: weight} summing to 1.0
    """
    inv_vols = {t: 1.0 / v for t, v in volatilities.items() if v > 0}
    total = sum(inv_vols.values())
    if total == 0:
        n = len(volatilities)
        return {t: 1.0 / n for t in volatilities}
    return {t: iv / total for t, iv in inv_vols.items()}


def apply_position_limits(
    weights: dict, max_weight: float = 0.20
) -> dict:
    """Cap each position at max_weight and redistribute excess proportionally."""
    capped = {}
    excess = 0.0
    uncapped_keys = []

    for t, w in weights.items():
        if w > max_weight:
            capped[t] = max_weight
            excess += w - max_weight
        else:
            capped[t] = w
            uncapped_keys.append(t)

    # Redistribute excess to uncapped positions
    while excess > 1e-9 and uncapped_keys:
        add_each = excess / len(uncapped_keys)
        new_uncapped = []
        excess = 0.0
        for t in uncapped_keys:
            new_w = capped[t] + add_each
            if new_w > max_weight:
                excess += new_w - max_weight
                capped[t] = max_weight
            else:
                capped[t] = new_w
                new_uncapped.append(t)
        uncapped_keys = new_uncapped

    # Normalize
    total = sum(capped.values())
    if total > 0:
        capped = {t: w / total for t, w in capped.items()}
    return capped


def calculate_trades(
    current_positions: dict,
    target_weights: dict,
    prices: dict,
    cash: float,
    max_exposure: float = 1.0,
) -> dict:
    """Calculate trades needed to move from current to target portfolio.

    Args:
        current_positions: {ticker: {"shares": float, "value": float}}
        target_weights: {ticker: weight} (sums to 1.0)
        prices: {ticker: current_price}
        cash: available cash
        max_exposure: max fraction of total portfolio to invest (from regime)

    Returns:
        {ticker: {"action": "buy"|"sell", "shares": float, "dollars": float}}
    """
    # Total portfolio value
    total_value = cash + sum(
        pos.get("value", 0) for pos in current_positions.values()
    )
    investable = total_value * max_exposure

    trades = {}

    # Sell positions not in target
    for ticker in current_positions:
        if ticker not in target_weights:
            pos = current_positions[ticker]
            trades[ticker] = {
                "action": "sell",
                "shares": pos["shares"],
                "dollars": pos["value"],
            }

    # Buy/adjust positions in target
    for ticker, weight in target_weights.items():
        target_value = investable * weight
        current_value = current_positions.get(ticker, {}).get("value", 0.0)
        diff = target_value - current_value
        price = prices.get(ticker, 0)

        if price <= 0:
            continue

        if diff > 0:
            buy_dollars = diff * (1 - COST_PER_SIDE)
            trades[ticker] = {
                "action": "buy",
                "shares": buy_dollars / price,
                "dollars": buy_dollars,
            }
        elif diff < -total_value * 0.01:  # only sell if diff > 1% of portfolio
            sell_dollars = abs(diff) * (1 - COST_PER_SIDE)
            trades[ticker] = {
                "action": "sell",
                "shares": sell_dollars / price,
                "dollars": sell_dollars,
            }

    return trades
