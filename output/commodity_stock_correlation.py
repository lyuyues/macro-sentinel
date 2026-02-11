"""
Commodity vs Stock Price & Forward PE Correlation Analysis
- Copper vs FCX (Freeport-McMoRan)
- Oil (WTI) vs XOM (ExxonMobil)
"""
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Fetch Data ──────────────────────────────────────────────
def fetch_data():
    end = datetime.now()
    start = end - timedelta(days=5*365)  # 5 years

    print("Fetching copper futures (HG=F)...")
    copper = yf.download("HG=F", start=start, end=end, progress=False)

    print("Fetching WTI crude oil (CL=F)...")
    oil = yf.download("CL=F", start=start, end=end, progress=False)

    print("Fetching FCX...")
    fcx = yf.download("FCX", start=start, end=end, progress=False)

    print("Fetching XOM...")
    xom = yf.download("XOM", start=start, end=end, progress=False)

    return copper, oil, fcx, xom


def get_forward_pe_history(ticker_str, price_df):
    """
    Approximate forward PE using trailing EPS from yfinance quarterly earnings.
    Forward PE = Price / Forward EPS (analyst consensus).
    Since historical forward PE isn't available via yfinance, we use trailing PE
    as a proxy and note current forward PE separately.
    """
    tk = yf.Ticker(ticker_str)

    # Get quarterly earnings for trailing EPS
    try:
        earnings = tk.quarterly_earnings
        if earnings is not None and len(earnings) > 0:
            print(f"  {ticker_str} quarterly earnings available: {len(earnings)} quarters")
    except:
        earnings = None

    # Get current forward PE from info
    info = tk.info
    forward_pe = info.get('forwardPE', None)
    trailing_pe = info.get('trailingPE', None)
    print(f"  {ticker_str} current Forward PE: {forward_pe}, Trailing PE: {trailing_pe}")

    # For historical PE, compute from quarterly financials
    try:
        income = tk.quarterly_income_stmt
        if income is not None and not income.empty:
            # Get diluted EPS row
            eps_rows = [r for r in income.index if 'Diluted EPS' in str(r)]
            if eps_rows:
                eps_quarterly = income.loc[eps_rows[0]]
                # Compute TTM EPS (rolling 4 quarters)
                eps_quarterly = eps_quarterly.sort_index()
                eps_ttm = eps_quarterly.rolling(4).sum()
                eps_ttm = eps_ttm.dropna()

                # Align with price data
                price_close = price_df['Close'].copy()
                if isinstance(price_close, pd.DataFrame):
                    price_close = price_close.iloc[:, 0]

                pe_series = pd.Series(dtype=float)
                for date, ttm_eps in eps_ttm.items():
                    if ttm_eps > 0:
                        # Find nearest price
                        date_ts = pd.Timestamp(date)
                        mask = price_close.index <= date_ts
                        if mask.any():
                            nearest_price = price_close[mask].iloc[-1]
                            pe_series[date_ts] = nearest_price / ttm_eps

                if len(pe_series) > 0:
                    # Interpolate to daily
                    pe_series.index = pd.DatetimeIndex(pe_series.index)
                    pe_daily = pe_series.reindex(price_close.index, method='ffill')
                    return pe_daily, forward_pe
    except Exception as e:
        print(f"  Warning: Could not compute historical PE for {ticker_str}: {e}")

    return None, forward_pe


def compute_correlation(s1, s2, label1, label2):
    """Compute rolling and overall correlation between two series."""
    # Align
    df = pd.DataFrame({label1: s1, label2: s2}).dropna()
    if len(df) < 30:
        return None, None, None

    overall_corr = df[label1].corr(df[label2])

    # Rolling 60-day correlation
    rolling_corr = df[label1].rolling(60).corr(df[label2])

    # Rolling 252-day (1 year) correlation
    rolling_corr_1y = df[label1].rolling(252).corr(df[label2])

    return overall_corr, rolling_corr, rolling_corr_1y


def plot_commodity_vs_stock(ax_main, commodity_prices, stock_prices, pe_series,
                            commodity_label, stock_label, forward_pe_current):
    """Plot commodity price, stock price, and PE on a chart."""
    # Flatten multi-level columns if needed
    if isinstance(commodity_prices, pd.DataFrame):
        commodity_close = commodity_prices['Close']
        if isinstance(commodity_close, pd.DataFrame):
            commodity_close = commodity_close.iloc[:, 0]
    else:
        commodity_close = commodity_prices

    if isinstance(stock_prices, pd.DataFrame):
        stock_close = stock_prices['Close']
        if isinstance(stock_close, pd.DataFrame):
            stock_close = stock_close.iloc[:, 0]
    else:
        stock_close = stock_prices

    color_commodity = '#E67E22'  # orange
    color_stock = '#2E86C1'     # blue
    color_pe = '#27AE60'        # green

    # Left axis: commodity price
    ax_main.plot(commodity_close.index, commodity_close.values,
                 color=color_commodity, linewidth=1.5, label=commodity_label, alpha=0.9)
    ax_main.set_ylabel(commodity_label, color=color_commodity, fontsize=11)
    ax_main.tick_params(axis='y', labelcolor=color_commodity)

    # Right axis: stock price
    ax_stock = ax_main.twinx()
    ax_stock.plot(stock_close.index, stock_close.values,
                  color=color_stock, linewidth=1.5, label=f'{stock_label} Price', alpha=0.9)
    ax_stock.set_ylabel(f'{stock_label} Price ($)', color=color_stock, fontsize=11)
    ax_stock.tick_params(axis='y', labelcolor=color_stock)

    # Third axis: PE ratio
    if pe_series is not None and len(pe_series.dropna()) > 5:
        ax_pe = ax_main.twinx()
        ax_pe.spines['right'].set_position(('axes', 1.12))
        ax_pe.plot(pe_series.index, pe_series.values,
                   color=color_pe, linewidth=1.2, label='Trailing PE', alpha=0.7, linestyle='--')
        ax_pe.set_ylabel('PE Ratio', color=color_pe, fontsize=11)
        ax_pe.tick_params(axis='y', labelcolor=color_pe)
        if forward_pe_current:
            ax_pe.axhline(y=forward_pe_current, color=color_pe, linestyle=':',
                         alpha=0.5, linewidth=1)
            ax_pe.annotate(f'Fwd PE: {forward_pe_current:.1f}',
                          xy=(stock_close.index[-1], forward_pe_current),
                          fontsize=9, color=color_pe, ha='right')

    ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax_main.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax_main.xaxis.get_majorticklabels(), rotation=45, ha='right')
    ax_main.grid(True, alpha=0.3)

    # Combined legend
    lines1, labels1 = ax_main.get_legend_handles_labels()
    lines2, labels2 = ax_stock.get_legend_handles_labels()
    if pe_series is not None and len(pe_series.dropna()) > 5:
        lines3, labels3 = ax_pe.get_legend_handles_labels()
        ax_main.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3,
                      loc='upper left', fontsize=9)
    else:
        ax_main.legend(lines1 + lines2, labels1 + labels2,
                      loc='upper left', fontsize=9)


def main():
    copper, oil, fcx, xom = fetch_data()

    print("\nComputing FCX PE history...")
    fcx_pe, fcx_fwd_pe = get_forward_pe_history("FCX", fcx)

    print("Computing XOM PE history...")
    xom_pe, xom_fwd_pe = get_forward_pe_history("XOM", xom)

    # ── Correlation Analysis ──────────────────────────────
    # Flatten Close columns
    copper_close = copper['Close'].iloc[:, 0] if isinstance(copper['Close'], pd.DataFrame) else copper['Close']
    oil_close = oil['Close'].iloc[:, 0] if isinstance(oil['Close'], pd.DataFrame) else oil['Close']
    fcx_close = fcx['Close'].iloc[:, 0] if isinstance(fcx['Close'], pd.DataFrame) else fcx['Close']
    xom_close = xom['Close'].iloc[:, 0] if isinstance(xom['Close'], pd.DataFrame) else xom['Close']

    print("\n" + "="*60)
    print("CORRELATION ANALYSIS")
    print("="*60)

    # Copper vs FCX
    corr_cu_fcx, roll_cu_fcx, roll_cu_fcx_1y = compute_correlation(
        copper_close, fcx_close, 'Copper', 'FCX')
    print(f"\nCopper vs FCX:")
    print(f"  Overall correlation (5yr): {corr_cu_fcx:.3f}")
    if roll_cu_fcx_1y is not None:
        print(f"  1Y rolling correlation range: {roll_cu_fcx_1y.min():.3f} ~ {roll_cu_fcx_1y.max():.3f}")
        print(f"  Current 1Y rolling corr: {roll_cu_fcx_1y.dropna().iloc[-1]:.3f}")

    # Oil vs XOM
    corr_oil_xom, roll_oil_xom, roll_oil_xom_1y = compute_correlation(
        oil_close, xom_close, 'Oil', 'XOM')
    print(f"\nWTI Oil vs XOM:")
    print(f"  Overall correlation (5yr): {corr_oil_xom:.3f}")
    if roll_oil_xom_1y is not None:
        print(f"  1Y rolling correlation range: {roll_oil_xom_1y.min():.3f} ~ {roll_oil_xom_1y.max():.3f}")
        print(f"  Current 1Y rolling corr: {roll_oil_xom_1y.dropna().iloc[-1]:.3f}")

    # Daily returns correlation (more meaningful)
    copper_ret = copper_close.pct_change().dropna()
    fcx_ret = fcx_close.pct_change().dropna()
    oil_ret = oil_close.pct_change().dropna()
    xom_ret = xom_close.pct_change().dropna()

    ret_corr_cu_fcx, _, _ = compute_correlation(copper_ret, fcx_ret, 'Copper_ret', 'FCX_ret')
    ret_corr_oil_xom, _, _ = compute_correlation(oil_ret, xom_ret, 'Oil_ret', 'XOM_ret')

    print(f"\nDaily Returns Correlation:")
    print(f"  Copper vs FCX returns: {ret_corr_cu_fcx:.3f}")
    print(f"  Oil vs XOM returns:    {ret_corr_oil_xom:.3f}")

    # ── Plotting ──────────────────────────────────────────
    fig = plt.figure(figsize=(18, 20))

    # Row 1: Copper vs FCX
    ax1 = fig.add_subplot(4, 1, 1)
    ax1.set_title(f'Copper Price vs FCX Stock Price & PE  (corr: {corr_cu_fcx:.2f})',
                  fontsize=14, fontweight='bold')
    plot_commodity_vs_stock(ax1, copper, fcx, fcx_pe,
                           'Copper ($/lb)', 'FCX', fcx_fwd_pe)

    # Row 2: Oil vs XOM
    ax2 = fig.add_subplot(4, 1, 2)
    ax2.set_title(f'WTI Crude Oil vs XOM Stock Price & PE  (corr: {corr_oil_xom:.2f})',
                  fontsize=14, fontweight='bold')
    plot_commodity_vs_stock(ax2, oil, xom, xom_pe,
                           'WTI Oil ($/bbl)', 'XOM', xom_fwd_pe)

    # Row 3: Rolling correlation — Copper vs FCX
    ax3 = fig.add_subplot(4, 1, 3)
    ax3.set_title('Rolling Correlation: Copper vs FCX', fontsize=14, fontweight='bold')
    if roll_cu_fcx is not None:
        ax3.plot(roll_cu_fcx.index, roll_cu_fcx.values, color='#E67E22',
                 linewidth=1, alpha=0.5, label='60-day rolling')
    if roll_cu_fcx_1y is not None:
        ax3.plot(roll_cu_fcx_1y.index, roll_cu_fcx_1y.values, color='#C0392B',
                 linewidth=2, label='252-day (1Y) rolling')
    ax3.axhline(y=corr_cu_fcx, color='gray', linestyle='--', alpha=0.5,
                label=f'Overall: {corr_cu_fcx:.2f}')
    ax3.axhline(y=0, color='black', linewidth=0.5)
    ax3.set_ylabel('Correlation')
    ax3.set_ylim(-1, 1)
    ax3.legend(loc='lower left')
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Row 4: Rolling correlation — Oil vs XOM
    ax4 = fig.add_subplot(4, 1, 4)
    ax4.set_title('Rolling Correlation: WTI Oil vs XOM', fontsize=14, fontweight='bold')
    if roll_oil_xom is not None:
        ax4.plot(roll_oil_xom.index, roll_oil_xom.values, color='#2E86C1',
                 linewidth=1, alpha=0.5, label='60-day rolling')
    if roll_oil_xom_1y is not None:
        ax4.plot(roll_oil_xom_1y.index, roll_oil_xom_1y.values, color='#8E44AD',
                 linewidth=2, label='252-day (1Y) rolling')
    ax4.axhline(y=corr_oil_xom, color='gray', linestyle='--', alpha=0.5,
                label=f'Overall: {corr_oil_xom:.2f}')
    ax4.axhline(y=0, color='black', linewidth=0.5)
    ax4.set_ylabel('Correlation')
    ax4.set_ylim(-1, 1)
    ax4.legend(loc='lower left')
    ax4.grid(True, alpha=0.3)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    outpath = os.path.join(OUTPUT_DIR, 'commodity_stock_correlation.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: {outpath}")
    plt.close()

    # ── Summary ───────────────────────────────────────────
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"""
Copper vs FCX:
  - Price correlation (5yr): {corr_cu_fcx:.2f}
  - Daily returns correlation: {ret_corr_cu_fcx:.2f}
  - FCX current Forward PE: {fcx_fwd_pe}
  - FCX tracks copper closely — it's essentially a leveraged copper play

WTI Oil vs XOM:
  - Price correlation (5yr): {corr_oil_xom:.2f}
  - Daily returns correlation: {ret_corr_oil_xom:.2f}
  - XOM current Forward PE: {xom_fwd_pe}
  - XOM has lower correlation with oil — more diversified (downstream, chemicals, LNG)
""")


if __name__ == "__main__":
    main()
