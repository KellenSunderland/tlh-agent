# TLH Agent

**Automated Tax-Loss Harvesting for Self-Directed Investors**

TLH Agent is an open-source tool that brings institutional-grade tax-loss harvesting strategies to individual investors. Build and manage your own direct indexing portfolio using commission-free brokerages, with intelligent automation to maximize your post-tax returns.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)

---

## Overview

Tax-loss harvesting (TLH) is a strategy that realizes investment losses to offset capital gains and reduce your tax liability. By selling securities at a loss and reinvesting in similar (but not identical) assets, you capture tax benefits while maintaining market exposure.

TLH Agent automates the monitoring, decision-making, and execution workflow for this strategy, turning what would require daily manual oversight into a managed process with configurable rules.

### Why Direct Indexing?

Instead of holding a single index ETF, direct indexing means owning the underlying individual stocks. This unlocks harvesting opportunities that don't exist with funds:

- On any given day, individual stocks move independently—some up, some down
- You can harvest losses on declining positions even when the overall index is flat or rising
- More granular control over your portfolio composition

### Key Features

- **Configurable Harvest Frequency** — Daily, weekly, or monthly scans for loss opportunities
- **Intelligent Rebuy Strategies** — Wait 31 days or immediately swap to similar securities
- **Wash Sale Prevention** — Automatic tracking to ensure IRS compliance
- **Rules Engine** — Customizable thresholds for loss significance, holding periods, and more
- **Brokerage Integration** — Manual trade lists for Robinhood, API automation for Alpaca
- **Position Tracking** — Lot-level cost basis management with FIFO/LIFO/specific ID support
- **Loss Carryforward Ledger** — Track harvested losses and their utilization across tax years
- **Native macOS App** — Clean tkinter-based interface for monitoring and configuration

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                           TLH Agent                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│   │   Portfolio  │───▶│    Rules     │───▶│   Trade Generation   │  │
│   │   Scanner    │    │    Engine    │    │                      │  │
│   └──────────────┘    └──────────────┘    └──────────────────────┘  │
│          │                   │                       │               │
│          ▼                   ▼                       ▼               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│   │  Price Feed  │    │  Wash Sale   │    │  Robinhood (Manual)  │  │
│   │    (Live)    │    │   Tracker    │    │  Alpaca (API)        │  │
│   └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

1. **Scanner** monitors your portfolio positions against current prices
2. **Rules Engine** evaluates each position against your configured thresholds
3. **Wash Sale Tracker** ensures any proposed trades won't violate IRS rules
4. **Trade Generator** produces actionable trade lists or executes via API

---

## Installation

### Requirements

- macOS 12.0 (Monterey) or later
- Python 3.11+

### Quick Install (Recommended)

```bash
# Install using uvx (no virtual environment needed)
uvx install tlh-agent
```

### Development Install

```bash
# Clone the repository
git clone https://github.com/yourusername/tlh-agent.git
cd tlh-agent

# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Run the application
uv run tlh-agent
```

---

## Configuration

TLH Agent uses a TOML configuration file located at `~/.config/tlh-agent/config.toml`.

### Harvest Frequency

Choose how often the agent scans for harvesting opportunities:

```toml
[scanner]
# Options: "daily", "weekly", "monthly"
frequency = "daily"

# For weekly: which day to scan (0 = Monday, 6 = Sunday)
weekly_scan_day = 4  # Friday

# For monthly: which day of month (1-28 recommended)
monthly_scan_day = 15

# Time of day to run scan (24h format, market hours recommended)
scan_time = "10:30"
```

**Frequency Considerations:**

| Frequency | Pros | Cons |
|-----------|------|------|
| Daily | Captures short-lived dips; maximizes harvest opportunities | More trades; faster basis erosion; higher cognitive load |
| Weekly | Balanced approach; reduces noise | May miss brief volatility |
| Monthly | Minimal maintenance; tactical approach | Misses most intra-month opportunities |

### Rebuy Strategy

Configure how the agent handles repurchasing after a harvest:

```toml
[rebuy]
# Options: "wait", "swap", "hybrid"
strategy = "swap"

# --- Wait Strategy Settings ---
# Simply wait 31 days then repurchase the original security
wait_days = 31

# --- Swap Strategy Settings ---
# Immediately purchase a similar (not substantially identical) security
# Optionally swap back to original after wash sale window

swap_back_enabled = true
swap_back_after_days = 32

# --- Hybrid Strategy Settings ---
# Use swaps for large positions, wait for small ones
hybrid_threshold_usd = 5000
```

**Strategy Comparison:**

| Strategy | Market Exposure | Complexity | Tracking Error |
|----------|-----------------|------------|----------------|
| **Wait** | Gap during 31-day window | Simple | None after rebuy |
| **Swap** | Continuous | Moderate | Slight, temporary |
| **Hybrid** | Continuous for large positions | Higher | Minimal |

### Swap Pair Mappings

Define which securities are acceptable swaps for each position:

```toml
[swap_pairs]
# Format: "ORIGINAL" = ["SWAP_1", "SWAP_2", ...]
# Agent will select first available swap not in wash sale window

# Broad market
"VTI" = ["ITOT", "SCHB", "SPTM"]
"VOO" = ["IVV", "SPY", "SPLG"]

# Sectors
"VGT" = ["XLK", "IYW", "FTEC"]
"VHT" = ["XLV", "IYH", "FHLC"]
"VFH" = ["XLF", "IYF", "FNCL"]

# International
"VXUS" = ["IXUS", "ACWX", "CWI"]
"VEA" = ["IEFA", "EFA", "SCHF"]
"VWO" = ["IEMG", "EEM", "SCHE"]

# Individual stocks - use sector ETF as swap
"AAPL" = ["XLK", "VGT"]
"JPM" = ["XLF", "VFH"]
```

### Rules Engine

Fine-tune when the agent recommends harvesting:

```toml
[rules]
# Minimum loss (in dollars) to consider harvesting
min_loss_usd = 100

# Minimum loss (as percentage of position) to consider harvesting
min_loss_pct = 3.0

# Only harvest losses that exceed transaction cost impact
min_tax_benefit_usd = 50

# Assumed tax rate for benefit calculations
assumed_tax_rate = 0.35

# Prefer short-term losses over long-term (higher tax value)
prefer_short_term = true

# Holding period thresholds
min_holding_days = 7          # Avoid harvesting very recent purchases
short_term_cutoff_days = 365  # Days until position becomes long-term

# Maximum percentage of portfolio to harvest in single scan
max_harvest_pct_per_scan = 10.0

# Exclude specific tickers from harvesting
excluded_tickers = ["BRK.A", "BRK.B"]
```

### Wash Sale Tracking

```toml
[wash_sale]
# Window for wash sale rule (30 days before + after = 61 day window)
window_days = 30

# Include external accounts in wash sale tracking
# (requires manual entry of external trades)
track_external_accounts = true

# Alert if a manual trade would trigger wash sale
warn_on_violation = true
```

---

## Brokerage Integration

### Robinhood (Manual Execution)

TLH Agent generates trade lists that you execute manually in Robinhood:

```toml
[brokerage]
provider = "robinhood"
mode = "manual"

# How to receive trade notifications
notification_method = "app"  # Options: "app", "email", "both"
email = "your@email.com"
```

When harvest opportunities are identified, you'll receive a notification with:
- Securities to sell (with quantities and expected loss)
- Corresponding securities to buy (if using swap strategy)
- Deadline for execution (to stay within scan window)

### Alpaca (API Automation)

For hands-off operation, connect directly to Alpaca's trading API:

```toml
[brokerage]
provider = "alpaca"
mode = "api"

# API credentials (use environment variables in production)
api_key_id = "${ALPACA_API_KEY}"
api_secret_key = "${ALPACA_SECRET_KEY}"

# Use paper trading for testing
paper_trading = true

# Execution settings
order_type = "limit"           # Options: "market", "limit"
limit_price_buffer_pct = 0.1   # For limit orders: % above/below market
max_retries = 3
retry_delay_seconds = 60

# Safety limits
require_confirmation = false   # If true, sends notification before executing
max_single_trade_usd = 50000
daily_trade_limit = 20
```

**Setting up Alpaca:**

1. Create an account at [alpaca.markets](https://alpaca.markets)
2. Generate API keys in your dashboard
3. Start with paper trading enabled to validate your configuration
4. Store your credentials securely using one of these methods:

**Option A: macOS Keychain (Recommended)**

Store credentials securely in the system keychain:

```bash
# Add your Alpaca API key
security add-generic-password -a "alpaca_api_key" -s "tlh-agent" -w "your-api-key"

# Add your Alpaca secret key
security add-generic-password -a "alpaca_secret_key" -s "tlh-agent" -w "your-secret-key"
```

To view stored credentials:
```bash
security find-generic-password -a "alpaca_api_key" -s "tlh-agent" -w
```

To delete credentials:
```bash
security delete-generic-password -a "alpaca_api_key" -s "tlh-agent"
security delete-generic-password -a "alpaca_secret_key" -s "tlh-agent"
```

**Option B: Environment Variables**

If no keychain credentials are found, the app falls back to environment variables:

```bash
export ALPACA_API_KEY="your-key-id"
export ALPACA_SECRET_KEY="your-secret-key"
```

---

## Portfolio Setup

### Initial Import

Import your existing positions to establish cost basis:

```bash
# From CSV export
tlh-agent import --file positions.csv --format robinhood

# From Alpaca API (automatic)
tlh-agent import --from-broker alpaca

# Manual entry
tlh-agent add-position --ticker AAPL --shares 100 --cost-basis 15000 --date 2024-01-15
```

### Building a Direct Index Portfolio

TLH Agent can help you build a direct index portfolio from scratch. Currently supported indexes:

- **Dow Jones Industrial Average (DJIA)** — 30 large-cap stocks, simple to fully replicate
- **S&P 500** — 500 large-cap stocks covering ~80% of US market capitalization

```bash
# Generate purchase list for S&P 500 constituents
tlh-agent build-index --index sp500 --amount 100000 --output purchases.csv

# Generate purchase list for Dow Jones
tlh-agent build-index --index djia --amount 50000 --output purchases.csv

# Exclude specific sectors or stocks
tlh-agent build-index --index sp500 --amount 100000 \
  --exclude-sectors "Energy,Utilities" \
  --exclude-tickers "META,GOOGL"
```

---

## Usage

### Launch the Application

```bash
# Start the GUI
tlh-agent

# Or run in CLI mode
tlh-agent scan --dry-run
```

### GUI Overview

The tkinter interface provides:

- **Dashboard** — Portfolio summary, unrealized gains/losses, harvest opportunities
- **Positions** — Detailed view of all holdings with lot-level cost basis
- **Trade Queue** — Pending trades (harvests, index buys, rebalances) awaiting approval
- **Wash Sale Calendar** — Visual timeline of restricted securities
- **Trade History** — Log of all executed harvests and rebuys
- **Loss Ledger** — Cumulative harvested losses and carryforward tracking
- **Settings** — Configuration editor with validation

### CLI Commands

```bash
# Run a harvest scan
tlh-agent scan

# Dry run (show what would be harvested without executing)
tlh-agent scan --dry-run

# Force scan outside normal schedule
tlh-agent scan --force

# View current wash sale restrictions
tlh-agent wash-sales

# Export tax documents
tlh-agent export --year 2024 --format csv

# View harvest history
tlh-agent history --year 2024

# Check carryforward losses
tlh-agent carryforward
```

---

## Tax Reporting

TLH Agent maintains records for tax filing:

```bash
# Generate Form 8949 data
tlh-agent export --year 2024 --format 8949

# Summary report for your accountant
tlh-agent export --year 2024 --format summary

# Full transaction log
tlh-agent export --year 2024 --format detailed
```

**Important:** TLH Agent provides transaction records to assist with tax preparation. Always consult a tax professional for your specific situation. The application does not provide tax advice.

---

## Development

### Setup

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/tlh-agent.git
cd tlh-agent
uv sync --dev
```

### Code Quality

The project uses `ruff` for linting/formatting and `ty` for type checking, both configured at medium strictness:

```bash
# Run linter
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type checking
uv run ty check
```

### Project Structure

```
tlh-agent/
├── pyproject.toml          # Project metadata and dependencies
├── src/
│   └── tlh_agent/
│       ├── __init__.py
│       ├── __main__.py     # Entry point
│       ├── app.py          # Main application / GUI
│       ├── scanner.py      # Portfolio scanning logic
│       ├── rules.py        # Rules engine
│       ├── wash_sale.py    # Wash sale tracking
│       ├── brokers/
│       │   ├── base.py     # Abstract broker interface
│       │   ├── robinhood.py
│       │   └── alpaca.py
│       ├── models/
│       │   ├── position.py
│       │   ├── trade.py
│       │   └── lot.py
│       └── ui/
│           ├── main_window.py
│           ├── dashboard.py
│           ├── positions.py
│           └── settings.py
├── tests/
│   ├── test_scanner.py
│   ├── test_rules.py
│   └── test_wash_sale.py
└── README.md
```

### Running Tests

```bash
uv run pytest
uv run pytest --cov=tlh_agent  # With coverage
```

### Visual UI Testing

The project includes a visual testing system that generates screenshots for UI validation. This enables AI-assisted review of UI changes.

**How it works:**

1. **Screenshot Generation** — Tests create a real tkinter window, navigate to each screen, and capture screenshots using PIL's ImageGrab
2. **AI Review** — Screenshots can be reviewed by multimodal AI (Claude) to assess visual quality, alignment, and design consistency
3. **Iterative Refinement** — Issues identified visually are fixed and re-tested

**Running visual tests:**

```bash
# Generate screenshots for all screens
uv run pytest tests/ui/ -v

# Screenshots saved to screenshots/ directory
ls screenshots/
# 01_dashboard.png  02_positions.png  03_trade_queue.png ...
```

**Test structure:**

```
tests/ui/
├── conftest.py          # Fixtures: app instance, screenshot capture
├── ui_test_helpers.py   # Widget inspection utilities
└── test_screens.py      # Screen tests and screenshot generation
```

**What gets validated:**

| Method | Purpose |
|--------|---------|
| `find_widgets_with_text()` | Verify expected text exists |
| `check_widgets_aligned_horizontally()` | Layout alignment checks |
| Screenshot review | Visual design quality (manual/AI) |

This approach combines automated functional tests with visual inspection, catching both logic errors and design regressions.

### Building for Distribution

```bash
# Build package
uv build

# Publish to PyPI (maintainers only)
uv publish
```

---

## Limitations & Disclaimers

- **Not Tax Advice** — This tool assists with trade execution. Consult a qualified tax professional for advice on your specific situation.
- **No Guarantees** — Tax-loss harvesting benefits depend on your individual circumstances, tax bracket, and future market conditions.
- **Wash Sale Complexity** — The tool tracks wash sales within its managed accounts. If you hold similar securities in other accounts (401k, IRA, spouse's accounts), you are responsible for avoiding wash sales across those accounts.
- **Basis Erosion** — Aggressive harvesting lowers your cost basis over time, creating larger taxable gains when you eventually sell. The strategy is most beneficial if you hold until death (stepped-up basis) or can time sales during low-income years.
- **macOS Only** — Current release supports macOS only. Linux and Windows support planned for future releases.

---

## Roadmap

- [ ] Linux and Windows support
- [ ] Additional index support (Nasdaq 100, Russell 2000, S&P 400 Mid Cap)
- [ ] Additional broker integrations (Interactive Brokers, Schwab, Fidelity)
- [ ] Rebalancing integration
- [ ] Municipal bond ladder tracking
- [ ] Mobile companion app for trade notifications

---

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

Built with:
- [uv](https://github.com/astral-sh/uv) — Fast Python package management
- [ruff](https://github.com/astral-sh/ruff) — Fast Python linter and formatter
- [Alpaca Markets](https://alpaca.markets) — Commission-free trading API