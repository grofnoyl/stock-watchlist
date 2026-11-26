"""Command-line interface for stock-watchlist."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .formatters import (
    format_pulse_json,
    format_pulse_markdown,
    format_pulse_text,
    format_quotes,
    format_watchlist,
)
from .models import WatchlistItem, normalize_symbol
from .pulse import QuoteProvider, build_market_pulse
from .storage import (
    default_config,
    load_watchlist,
    remove_item,
    resolve_watchlist_path,
    save_watchlist,
    upsert_item,
)
from .yahoo import YahooFinanceClient


def _filter_by_market(items: list[WatchlistItem], market: str) -> list[WatchlistItem]:
    if market == "all":
        return items
    target = market.upper()
    return [item for item in items if item.market == target]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-watchlist",
        description="Lean IDX & US stock watchlist and Market Pulse CLI for Hermes Agent.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-f",
        "--file",
        dest="watchlist_file",
        default=None,
        help="Path to watchlist JSON file (defaults to STOCK_WATCHLIST_FILE, ./watchlist.json, or ~/.config/stock-watchlist/watchlist.json).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds for Yahoo Finance requests (default: 10).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Create a starter watchlist JSON file.")
    p_init.add_argument(
        "--preset",
        choices=("all", "idx", "us"),
        default="all",
        help="Starter ticker preset (default: all).",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing watchlist file.",
    )

    # list
    p_list = subparsers.add_parser("list", help="List tracked tickers in the watchlist.")
    p_list.add_argument(
        "--format",
        choices=("markdown", "json", "text"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    p_list.add_argument(
        "--market",
        choices=("all", "idx", "us"),
        default="all",
        help="Filter tickers by market (default: all).",
    )

    # add
    p_add = subparsers.add_parser("add", help="Add or update a ticker in the watchlist.")
    p_add.add_argument("symbol", help="Ticker symbol (e.g. BBCA.JK, NVDA, or BBCA with --idx).")
    p_add.add_argument(
        "--idx",
        action="store_true",
        help="Automatically append .JK suffix for Indonesian (IDX) tickers.",
    )
    p_add.add_argument("--name", default=None, help="Optional display alias.")
    p_add.add_argument("--buy-below", type=float, default=None, help="Alert when price <= value.")
    p_add.add_argument("--sell-above", type=float, default=None, help="Alert when price >= value.")
    p_add.add_argument("--note", default=None, help="Optional short note.")

    # remove
    p_remove = subparsers.add_parser("remove", help="Remove a ticker from the watchlist.")
    p_remove.add_argument("symbol", help="Ticker symbol to remove.")
    p_remove.add_argument(
        "--idx",
        action="store_true",
        help="Automatically append .JK suffix for Indonesian (IDX) tickers.",
    )

    # quote
    p_quote = subparsers.add_parser("quote", help="Fetch ad-hoc quotes for one or more tickers.")
    p_quote.add_argument("symbols", nargs="+", help="One or more ticker symbols.")
    p_quote.add_argument(
        "--idx",
        action="store_true",
        help="Automatically append .JK suffix to tickers without an exchange suffix.",
    )
    p_quote.add_argument(
        "--format",
        choices=("markdown", "json", "text"),
        default="markdown",
        help="Output format (default: markdown).",
    )

    # pulse
    p_pulse = subparsers.add_parser(
        "pulse",
        help="Fetch live quotes, 1D/5D moves, alerts, and Market Pulse summary.",
    )
    p_pulse.add_argument(
        "--format",
        choices=("markdown", "json", "text"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    p_pulse.add_argument(
        "--market",
        choices=("all", "idx", "us"),
        default="all",
        help="Filter watchlist items by market (default: all).",
    )
    p_pulse.add_argument(
        "--no-benchmarks",
        action="store_true",
        help="Skip fetching market benchmark indices.",
    )
    p_pulse.add_argument(
        "--benchmarks",
        default=None,
        help="Comma-separated benchmark tickers overriding config (e.g. ^JKSE,^GSPC).",
    )
    p_pulse.add_argument(
        "--only-alerts",
        action="store_true",
        help="Render only triggered buy/sell alerts (useful for quiet cron jobs).",
    )
    p_pulse.add_argument(
        "--exit-on-alert",
        action="store_true",
        help="Exit with code 2 when one or more price alerts are triggered.",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    provider: QuoteProvider | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    watchlist_path: Path = resolve_watchlist_path(args.watchlist_file)

    if args.command == "init":
        if watchlist_path.exists() and not args.force:
            print(
                f"Watchlist already exists at {watchlist_path}. Use --force to overwrite.",
                file=sys.stderr,
            )
            return 1
        cfg = default_config(args.preset)
        save_watchlist(watchlist_path, cfg)
        print(f"Initialized watchlist ({args.preset}, {len(cfg.items)} tickers) at {watchlist_path}")
        return 0

    if args.command == "list":
        cfg = load_watchlist(watchlist_path)
        items = _filter_by_market(cfg.items, args.market)
        print(format_watchlist(items, args.format))
        return 0

    if args.command == "add":
        cfg = load_watchlist(watchlist_path)
        item, created = upsert_item(
            cfg,
            args.symbol,
            idx=args.idx,
            name=args.name,
            buy_below=args.buy_below,
            sell_above=args.sell_above,
            note=args.note,
        )
        save_watchlist(watchlist_path, cfg)
        action = "Added" if created else "Updated"
        print(f"{action} {item.symbol} ({item.market}) in {watchlist_path}")
        return 0

    if args.command == "remove":
        cfg = load_watchlist(watchlist_path)
        removed = remove_item(cfg, args.symbol, idx=args.idx)
        if not removed:
            norm = normalize_symbol(args.symbol, idx=args.idx)
            print(f"Ticker {norm} not found in {watchlist_path}", file=sys.stderr)
            return 1
        save_watchlist(watchlist_path, cfg)
        print(f"Removed {normalize_symbol(args.symbol, idx=args.idx)} from {watchlist_path}")
        return 0

    client: QuoteProvider = provider or YahooFinanceClient(timeout=args.timeout)

    if args.command == "quote":
        symbols = [normalize_symbol(s, idx=args.idx) for s in args.symbols]
        quotes, errors = client.fetch_quotes(symbols)
        print(format_quotes(quotes, errors, args.format))
        return 0 if quotes else 1

    if args.command == "pulse":
        cfg = load_watchlist(watchlist_path)
        items = _filter_by_market(cfg.items, args.market)
        if not items:
            if args.format == "json":
                print(json.dumps({"error": "Watchlist is empty.", "file": str(watchlist_path)}))
            else:
                print(
                    f"Watchlist is empty ({watchlist_path}). Run `stock-watchlist init` or `stock-watchlist add` first.",
                    file=sys.stderr,
                )
            return 1

        benchmarks = (
            [normalize_symbol(b) for b in args.benchmarks.split(",") if b.strip()]
            if args.benchmarks
            else cfg.benchmarks
        )

        report = build_market_pulse(
            items,
            client,
            benchmarks=benchmarks,
            include_benchmarks=not args.no_benchmarks,
        )

        if args.format == "json":
            print(format_pulse_json(report))
        elif args.format == "text":
            print(format_pulse_text(report, only_alerts=args.only_alerts))
        else:
            print(format_pulse_markdown(report, only_alerts=args.only_alerts))

        if not report.quotes and report.errors:
            return 1
        if args.exit_on_alert and report.alerts:
            return 2
        return 0

    return 1
