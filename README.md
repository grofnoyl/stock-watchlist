# stock-watchlist

Lean, zero-dependency Python 3 CLI and **Hermes Agent** skill for tracking **IDX (`.JK`) & US** stock watchlists and generating daily **Market Pulse** briefings via Yahoo Finance (no API key required).

## Features

- **Zero runtime dependencies** — pure Python 3.10+ standard library (fast startup, easy cron & Hermes deployment).
- **IDX & US Market Support** — handles `.JK` (IDR), US (USD), indices (`^JKSE`, `^GSPC`, `^IXIC`), and FX (`USDIDR=X`) with currency-aware formatting.
- **Market Pulse Briefings** — concurrent quote fetching with 1D change, 5D change, day range, volume, market breadth (`up / down / flat`), average move, and top gainers/losers.
- **Price Target Alerts** — optional `buy_below` and `sell_above` thresholds per ticker with cron-friendly `--only-alerts` and `--exit-on-alert` (exit code `2`).
- **Hermes-Ready Output** — switch cleanly between `markdown`, `json`, and compact `text`.
- **Bundled Hermes Skill** — includes [`skills/stock-watchlist/SKILL.md`](skills/stock-watchlist/SKILL.md).

## Quickstart

```bash
# Install editable CLI (optional — you can also run via `PYTHONPATH=src python3 -m stock_watchlist`)
pip install -e .

# Initialize starter watchlist (IDX + US)
stock-watchlist init --preset all

# Run Market Pulse briefing
stock-watchlist pulse

# JSON output for Hermes / automation
stock-watchlist pulse --format json

# Quick ad-hoc quote check
stock-watchlist quote BBCA.JK BBRI.JK NVDA AAPL
```

## Watchlist Management

Watchlist location lookup order:
1. `-f / --file <path>`
2. `STOCK_WATCHLIST_FILE` environment variable
3. `./watchlist.json` (if present in current directory)
4. `~/.config/stock-watchlist/watchlist.json`

```bash
# Add / update tickers (use --idx to auto-append .JK)
stock-watchlist add BBCA --idx --name "Bank Central Asia" --buy-below 9000 --sell-above 11000
stock-watchlist add NVDA --buy-below 110 --note "AI core"

# List watchlist (all, idx, or us)
stock-watchlist list --market all --format markdown

# Remove ticker
stock-watchlist remove TLKM --idx
```

## Hermes Agent Integration

Copy or symlink the bundled skill into your Hermes skills directory:

```bash
mkdir -p ~/.hermes/skills
ln -s "$(pwd)/skills/stock-watchlist" ~/.hermes/skills/stock-watchlist
```

### Cron Examples (WIB / Asia/Jakarta)

```cron
# IDX closing Market Pulse (Mon-Fri 16:15 WIB)
15 16 * * 1-5 stock-watchlist pulse --market idx --format markdown

# US market close Market Pulse (Tue-Sat 05:30 WIB)
30 5 * * 2-6 stock-watchlist pulse --market us --format markdown

# Hourly alert check (returns exit code 2 when any threshold triggers)
0 * * * 1-5 stock-watchlist pulse --only-alerts --exit-on-alert --format text
```

## Development & Tests

```bash
pytest -v
```
