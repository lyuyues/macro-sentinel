# macro-sentinel

FRED-driven macro market sentiment monitor — 19 indicators, 6 core questions, one signal.

## What it does

Fetches 19 key FRED series (inflation, employment, financial conditions, leading indicators), answers 6 core questions about macro risk, and produces:

- Markdown report with detailed data tables
- Colored terminal summary
- macOS notification on signal change

## The 6 Questions

| # | Question | What it checks |
|---|----------|----------------|
| 1 | Services inflation sticky? | CPI Services 3M annualized trend |
| 2 | Inflation expectations unanchored? | 5Y breakeven + 5Y5Y forward level |
| 3 | Wage-price spiral? | Avg hourly earnings YoY vs Core CPI YoY |
| 4 | Labor market deteriorating? | Unemployment delta + ICSA acceleration |
| 5 | Financial conditions tightening? | NFCI + HY spread + yield curve + VIX |
| 6 | Economic momentum weakening? | Consumer sentiment + Manufacturing IP + Recession probability |

## Usage

```bash
python macro_monitor.py                  # Run once, save report
python macro_monitor.py --check-only     # Terminal only, no file saved
python macro_monitor.py --test-alert     # Test macOS notification
python macro_monitor.py --install        # Install launchd (monthly 15th)
python macro_monitor.py --uninstall      # Uninstall launchd
```

## Requirements

```
pandas
numpy
requests
fredapi  # optional, falls back to FRED CSV endpoint
```

Set `FRED_API_KEY` env var for API access, or leave unset to use the public CSV endpoint.

## Output

Reports saved to `output/macro_monitor/macro_report_YYYY-MM-DD.md`.
