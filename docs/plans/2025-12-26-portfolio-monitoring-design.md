# Portfolio Monitoring System Design

**Date**: 2025-12-26
**Goal**: Automated portfolio monitoring with educational insights about financial signals

## System Overview

A multi-agent system that automatically monitors stocks, calculates DCF valuations, generates buy/sell signals, and creates educational reports explaining the financial reasoning.

### Key Objectives
- Automate daily/weekly portfolio monitoring
- Support multiple watchlist sources (manual, indices, dynamic screening)
- Generate actionable signals: DCF undervaluation, trend changes, risk scores, position sizing
- Provide educational insights to help learn financial analysis
- Start simple (file-based) with clean migration path to cloud infrastructure

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator                          │
│         (Coordinates agents & workflow)                  │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Data Fetcher │───▶│  Valuation   │───▶│   Signal     │
│    Agent     │    │    Agent     │    │  Generator   │
└──────────────┘    └──────────────┘    └──────────────┘
                                                 │
                                                 ▼
                                        ┌──────────────┐
                                        │   Report     │
                                        │  Generator   │
                                        └──────────────┘
```

### Design Principles
1. **Single Responsibility**: Each agent has one clear purpose
2. **Data Contracts**: Agents communicate through well-defined schemas
3. **Independence**: Agents can run separately for testing/debugging
4. **Extensibility**: Easy to add new agents or modify existing ones
5. **Migration-Ready**: Abstracted storage layer for file → cloud transition

## Agent Specifications

### 1. Data Fetcher Agent

**Purpose**: Acquire and cache financial data from SEC EDGAR API

**Responsibilities**:
- Read watchlist sources (manual CSV, index configs, screening rules)
- Expand indices to ticker lists (S&P 500, NASDAQ 100, etc.)
- Apply dynamic screening criteria (market cap, sector filters)
- Fetch financial data from SEC EDGAR `companyfacts` API
- Handle rate limiting (10 requests/second SEC limit)
- Cache raw data to avoid redundant API calls
- Retry logic for network failures
- Validate data completeness

**Input**:
- `input/watchlist.csv` - Manual ticker list
- `input/indices.yaml` - Index-based auto-discovery config
- `input/screening_rules.yaml` - Dynamic screening criteria

**Output**:
- `data/raw_financials/{ticker}/{date}.json` - Cached SEC data
- `data/stock_universe.csv` - Consolidated list of all tickers
- `data/fetch_errors.csv` - Failed tickers for review

**Key Features**:
- Parallel fetching with asyncio + semaphore for rate limiting
- Smart caching: only refetch if data older than 24 hours
- Comprehensive error tracking and logging

---

### 2. Valuation Agent

**Purpose**: Calculate DCF fair values using 3-stage 10-year model

**Responsibilities**:
- Read raw financial data from Data Fetcher
- Run DCF calculations (reuses existing `dcf_builder.py` logic)
- Calculate: FCF, margins, growth rates, fair value per share
- Handle edge cases: negative FCF, missing years, outlier ratios
- Store valuation history for trend analysis
- Quality scoring: flag low-confidence valuations

**Input**:
- `data/raw_financials/{ticker}/*.json`
- `data/stock_universe.csv`
- User parameters: required return, perpetual growth rate

**Output**:
- `data/valuations/{ticker}_history.csv` - Time series of fair values
- `data/valuations/latest.csv` - Most recent fair value for all stocks

**Valuation Model**: 3-Stage 10-Year DCF
1. **Years 1-5**: Fast growth (sector-based, analyst forecasts or revenue CAGR)
2. **Years 6-10**: Stable growth (convergence to sector average)
3. **Terminal**: Perpetual growth (conservative sector-based rate)

**Quality Score Factors**:
- Data completeness (missing years penalized)
- Ratio stability (high FCF/NI volatility penalized)
- Margin reasonableness (extreme values flagged)

---

### 3. Signal Generator Agent

**Purpose**: Generate actionable buy/sell/hold signals with risk assessment

**Responsibilities**:
- Fetch current market prices (yfinance or similar)
- Compare market price vs DCF fair value
- Calculate undervaluation/overvaluation percentages
- Detect fair value trend changes (business quality shifts)
- Calculate risk scores (FCF volatility, margin stability, sector factors)
- Generate position sizing recommendations
- Create signal history for backtesting

**Input**:
- `data/valuations/latest.csv`
- Current market prices (API fetch)
- `data/valuations/{ticker}_history.csv` (for trend analysis)

**Output**:
- `data/signals/latest.json` - Current signals for all stocks
- `data/signals/history/{date}.json` - Signal archive

**Signal Types**:

1. **Value Signal** (DCF Undervaluation):
   - **Buy**: Current price >20% below fair value
   - **Sell**: Current price >20% above fair value
   - **Hold**: Within ±20% of fair value

2. **Trend Signal** (Business Quality):
   - **Alert**: Fair value changed >15% in last quarter
   - Direction: Improving (↑) or Deteriorating (↓)

3. **Risk Score** (0-100, lower = safer):
   - FCF volatility (past 5 years)
   - Net margin stability
   - Sector risk adjustment
   - Valuation confidence score

4. **Position Sizing**:
   - High conviction (>30% undervalued, risk <30): 5-8% of portfolio
   - Medium conviction (20-30% undervalued, risk 30-60): 3-5%
   - Low conviction (<20% or risk >60): 1-2%

---

### 4. Report Generator Agent

**Purpose**: Create human-readable reports with educational insights

**Responsibilities**:
- Read signals and valuation data
- Generate HTML/markdown reports
- Explain financial concepts (FCF, CAGR, perpetual growth, etc.)
- Show calculation breakdowns for each recommendation
- Create visual summaries (top opportunities, risk distribution)
- Compare stocks side-by-side for pattern recognition

**Input**:
- `data/signals/latest.json`
- `data/valuations/latest.csv`
- `data/raw_financials/` (for detailed breakdowns)

**Output**:
- `output/reports/{date}_portfolio_report.html` - Main report
- `output/reports/{date}_educational_insights.md` - Learning content

**Report Sections**:

1. **Executive Summary**
   - Top 10 buy opportunities
   - Top 10 sell candidates
   - Portfolio health overview

2. **Signal Breakdown**
   - Each stock with active signal
   - Calculation details (revenue, FCF, growth assumptions)
   - Why this signal was generated

3. **Educational Insights**
   - Concept explanations (DCF, FCF margin, sector assumptions)
   - Real examples from current signals
   - Pattern recognition tips

4. **Risk Analysis**
   - Risk distribution across portfolio
   - High-risk holdings flagged
   - Diversification recommendations

## Data Architecture

### Directory Structure

```
AI_stock_analysis/
├── agents/
│   ├── __init__.py
│   ├── data_fetcher.py      # Data Fetcher Agent
│   ├── valuation.py          # Valuation Agent
│   ├── signal_generator.py   # Signal Generator Agent
│   └── report_generator.py   # Report Generator Agent
├── orchestrator/
│   ├── __init__.py
│   ├── pipeline.py           # Main workflow coordinator
│   └── scheduler.py          # Cron/scheduling logic
├── shared/
│   ├── __init__.py
│   ├── config.py             # Shared configuration
│   ├── data_contracts.py     # Data schemas/validation
│   └── utils.py              # Common utilities
├── input/
│   ├── watchlist.csv         # Manual ticker list
│   ├── indices.yaml          # Index-based discovery
│   └── screening_rules.yaml  # Dynamic screening criteria
├── data/
│   ├── raw_financials/       # SEC data cache
│   ├── stock_universe.csv    # All tickers to analyze
│   ├── valuations/           # DCF results
│   ├── signals/              # Buy/sell signals
│   └── fetch_errors.csv      # Error tracking
├── output/
│   └── reports/              # Generated reports
├── dcf_builder.py            # Existing DCF code (kept)
├── dcf_utils.py              # Existing utilities (kept)
└── main.py                   # Entry point
```

### Data Contracts

#### Stock Universe Schema (`data/stock_universe.csv`)

```csv
ticker,source,sector,market_cap,last_updated
AAPL,manual_watchlist,TECH,2800000,2025-12-26
TSLA,sp500_index,CONSUMER,800000,2025-12-26
GOOGL,screening_megacap,TECH,1700000,2025-12-26
```

**Fields**:
- `ticker`: Stock symbol
- `source`: How this stock was added (manual_watchlist, sp500_index, screening_megacap, etc.)
- `sector`: Mapped sector (TECH, CONSUMER, BANK, INSURANCE, ENERGY, PHARMA)
- `market_cap`: Market capitalization in millions
- `last_updated`: When this entry was last refreshed

#### Valuation Output Schema (`data/valuations/latest.csv`)

```csv
ticker,fair_value,last_updated,fcf_margin,growth_fast,growth_stable,growth_terminal,confidence_score
AAPL,185.50,2025-12-26,0.28,0.12,0.08,0.025,0.85
TSLA,220.00,2025-12-26,0.05,0.25,0.15,0.03,0.62
```

**Fields**:
- `ticker`: Stock symbol
- `fair_value`: DCF fair value per share
- `last_updated`: Calculation timestamp
- `fcf_margin`: FCF as % of revenue
- `growth_fast`: Years 1-5 growth rate
- `growth_stable`: Years 6-10 growth rate
- `growth_terminal`: Perpetual growth rate
- `confidence_score`: 0-1 (data quality indicator)

#### Signal Output Schema (`data/signals/latest.json`)

```json
{
  "AAPL": {
    "ticker": "AAPL",
    "current_price": 175.20,
    "fair_value": 185.50,
    "undervaluation_pct": 5.55,
    "value_signal": "HOLD",
    "trend_signal": "IMPROVING",
    "trend_change_pct": 8.2,
    "risk_score": 25,
    "position_size_pct": 0,
    "recommendation": "Hold - fairly valued, business improving",
    "last_updated": "2025-12-26T18:00:00"
  },
  "TSLA": {
    "ticker": "TSLA",
    "current_price": 165.00,
    "fair_value": 220.00,
    "undervaluation_pct": 25.00,
    "value_signal": "BUY",
    "trend_signal": "STABLE",
    "trend_change_pct": 2.1,
    "risk_score": 65,
    "position_size_pct": 3.0,
    "recommendation": "Buy - undervalued but high risk, small position",
    "last_updated": "2025-12-26T18:00:00"
  }
}
```

## Workflow & Orchestration

### Daily Batch Process

```python
# orchestrator/pipeline.py

def run_daily_pipeline():
    """
    Execute full monitoring pipeline
    """

    # 1. Data Fetcher Agent
    logger.info("Step 1: Fetching financial data...")
    stock_universe = data_fetcher.run(
        watchlist_file='input/watchlist.csv',
        indices_config='input/indices.yaml',
        screening_rules='input/screening_rules.yaml'
    )
    # Output: data/stock_universe.csv, data/raw_financials/

    # 2. Valuation Agent
    logger.info("Step 2: Calculating DCF valuations...")
    valuations = valuation_agent.run(
        stock_universe=stock_universe,
        required_return=0.07,
        perpetual_growth=0.025
    )
    # Output: data/valuations/latest.csv, data/valuations/{ticker}_history.csv

    # 3. Signal Generator Agent
    logger.info("Step 3: Generating signals...")
    signals = signal_generator.run(
        valuations=valuations
    )
    # Output: data/signals/latest.json, data/signals/history/{date}.json

    # 4. Report Generator Agent
    logger.info("Step 4: Creating reports...")
    report_generator.run(
        signals=signals,
        valuations=valuations
    )
    # Output: output/reports/{date}_portfolio_report.html

    logger.info("Pipeline complete!")
```

### Scheduling Options

**Option A - System Cron Job** (simple):
```bash
# Run daily at 6 PM after market close (EST)
0 18 * * * cd /path/to/AI_stock_analysis && python main.py --mode daily
```

**Option B - Python Built-in Scheduler**:
```python
# orchestrator/scheduler.py
import schedule
import time

def job():
    run_daily_pipeline()

schedule.every().day.at("18:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run with: `python main.py --schedule daily`

## Migration Path: Files → Cloud

### Phase 1: File-Based Storage (Current)

All data in CSV/JSON files:
- Simple, version-controllable, no infrastructure
- Works well for <10K stocks monitored
- Easy to inspect and debug

### Phase 2: Abstracted Storage Layer (Migration Prep)

```python
# shared/storage.py

class StorageBackend(ABC):
    @abstractmethod
    def save_valuations(self, data: pd.DataFrame) -> None:
        pass

    @abstractmethod
    def load_valuations(self) -> pd.DataFrame:
        pass

class FileStorage(StorageBackend):
    """Current implementation"""
    def save_valuations(self, data):
        data.to_csv('data/valuations/latest.csv')

    def load_valuations(self):
        return pd.read_csv('data/valuations/latest.csv')

class CloudStorage(StorageBackend):
    """Future PostgreSQL/MongoDB implementation"""
    def save_valuations(self, data):
        # Write to cloud database
        pass

    def load_valuations(self):
        # Read from cloud database
        pass
```

### Phase 3: Cloud Migration

**Migration steps**:
1. Implement `CloudStorage` class with PostgreSQL/MongoDB
2. Update `shared/config.py`: change `STORAGE_BACKEND = 'cloud'`
3. Migrate historical data with migration script
4. Agents remain unchanged (use abstracted storage)

**Benefits**:
- No agent code changes required
- Can test both storage backends in parallel
- Rollback by changing config

## Configuration

### `shared/config.py`

```python
# Storage
STORAGE_BACKEND = 'file'  # 'file' or 'cloud'

# Data Fetcher
SEC_RATE_LIMIT = 10  # requests per second
CACHE_EXPIRY_HOURS = 24

# Valuation
DEFAULT_REQUIRED_RETURN = 0.07
DEFAULT_PERPETUAL_GROWTH = 0.025
DEFAULT_AVG_YEARS = 5

# Signal Generator
VALUE_BUY_THRESHOLD = 0.20  # 20% undervalued
VALUE_SELL_THRESHOLD = 0.20  # 20% overvalued
TREND_ALERT_THRESHOLD = 0.15  # 15% fair value change

# Position Sizing
HIGH_CONVICTION_SIZE = 0.07  # 7% of portfolio
MEDIUM_CONVICTION_SIZE = 0.04  # 4%
LOW_CONVICTION_SIZE = 0.02  # 2%

# Risk Scoring
RISK_LOW_THRESHOLD = 30
RISK_HIGH_THRESHOLD = 60
```

### Input File Examples

**`input/watchlist.csv`**:
```csv
ticker
AAPL
GOOGL
MSFT
TSLA
```

**`input/indices.yaml`**:
```yaml
indices:
  - name: sp500
    source: wikipedia
    url: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies

  - name: nasdaq100
    source: wikipedia
    url: https://en.wikipedia.org/wiki/Nasdaq-100
```

**`input/screening_rules.yaml`**:
```yaml
screens:
  - name: megacap_tech
    filters:
      - market_cap: ">100000"  # >$100B
      - sector: "TECH"

  - name: undervalued_consumer
    filters:
      - sector: "CONSUMER"
      - pe_ratio: "<20"
```

## Testing Strategy

### Unit Tests
- Each agent tested independently
- Mock data contracts (no real API calls)
- Edge case handling (missing data, negative FCF, etc.)

### Integration Tests
- End-to-end pipeline with sample data
- Verify data flow between agents
- Validate output schemas

### Validation Tests
- Compare new DCF calculations vs existing `dcf_builder.py`
- Ensure backward compatibility
- Spot-check known stocks (AAPL, GOOGL, etc.)

## Success Criteria

### Functional Requirements
- ✓ System runs daily without manual intervention
- ✓ Supports all three watchlist sources
- ✓ Generates all four signal types
- ✓ Creates educational reports
- ✓ Handles errors gracefully (logs failures, continues processing)

### Performance Requirements
- Process 100 stocks in <30 minutes
- SEC API rate limits respected
- Cache hit rate >80% (avoid redundant fetches)

### Quality Requirements
- DCF calculations match existing `dcf_builder.py` within 1%
- Signal accuracy validated through backtesting
- Reports are clear and educational

## Future Enhancements

### Near-term
- Email/Slack notifications for high-conviction signals
- Backtesting framework to validate signal accuracy
- Portfolio tracking (track actual holdings vs recommendations)

### Long-term
- Real-time monitoring with websockets
- Machine learning for growth rate predictions
- Multi-factor models (combine DCF with other strategies)
- Web dashboard for interactive exploration

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| SEC API rate limits | Pipeline fails | Implement exponential backoff, cache aggressively |
| Missing financial data | Incomplete valuations | Quality scoring, flag low-confidence results |
| Market data API costs | Expensive at scale | Start with free tier (yfinance), upgrade if needed |
| Storage scaling (file-based) | Performance degrades | Abstract storage early, plan cloud migration |
| DCF model limitations | Inaccurate valuations | Educational reports explain assumptions/limitations |

## Conclusion

This system provides automated, educational portfolio monitoring built on your existing DCF methodology. The modular agent architecture allows independent development and testing, while the abstracted storage layer ensures smooth migration to cloud infrastructure when needed.

**Next Steps**: Create detailed implementation plan breaking down each agent into specific coding tasks.
