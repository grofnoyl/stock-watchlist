---
name: stock-watchlist
description: Track IDX (.JK) and US stock watchlists, check live quotes, and generate daily Market Pulse summaries (Markdown or JSON) using Yahoo Finance with zero API keys.
---

# Stock Watchlist & Market Pulse (Hermes Skill)

Use the `stock-watchlist` CLI (zero third-party runtime dependencies, Python 3.10+) to check Indonesian (IDX / `.JK`) and US equities, benchmarks (`^JKSE`, `^GSPC`, `^IXIC`, `USDIDR=X`), and price target alerts.

## Invocation

If installed via `pip install -e .`, invoke `stock-watchlist`. Otherwise run directly from the repo with:

```bash
PYTHONPATH=/path/to/stock-watchlist/src python3 -m stock_watchlist <command>
```

## Common Commands

### 1. Daily Market Pulse (for user briefing or cron)
```bash
# Full Markdown briefing (IDX + US + benchmarks + top movers + alerts)
stock-watchlist pulse --format markdown

# Machine-readable JSON for structured agent reasoning
stock-watchlist pulse --format json

# IDX-only or US-only briefing
stock-watchlist pulse --market idx --format markdown
stock-watchlist pulse --market us --format markdown

# Quiet cron alert check (exits with code 2 when any buy/sell threshold triggers)
stock-watchlist pulse --only-alerts --exit-on-alert --format text
```

### 2. Ad-hoc Quote Lookup
```bash
# Mix IDX (.JK) and US tickers
stock-watchlist quote BBCA.JK BBRI.JK NVDA AAPL --format markdown

# Shorthand for IDX tickers without typing .JK
stock-watchlist quote BBCA BMRI TLKM --idx --format json
```

### 3. Manage Watchlist
```bash
# Create starter watchlist (presets: all, idx, us)
stock-watchlist init --preset all

# List current watchlist
stock-watchlist list --format markdown

# Add or update a ticker with optional target alerts
stock-watchlist add BBCA --idx --name "Bank Central Asia" --buy-below 9000 --sell-above 11000 --note "Core bank"
stock-watchlist add NVDA --buy-below 110 --note "AI core"

# Remove a ticker
stock-watchlist remove TLKM --idx
```

## Conventions for Hermes Responses
- **IDX tickers** end in `.JK` (e.g. `BBCA.JK`, `BBRI.JK`, `BMRI.JK`, `TLKM.JK`); use `--idx` if the user gives bare 4-letter Indonesian codes.
- **US tickers** have no suffix (e.g. `NVDA`, `AAPL`, `MSFT`, `BRK-B`).
- Prefer `--format json` when you need to analyze, filter, or combine quotes with other tools; prefer `--format markdown` when delivering a direct Market Pulse briefing.
- Custom watchlist files can be passed via `-f /path/to/watchlist.json` or the `STOCK_WATCHLIST_FILE` environment variable.
