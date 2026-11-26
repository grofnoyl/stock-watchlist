"""Tests for Market Pulse analytics, summary, and alert evaluation."""

from __future__ import annotations

from datetime import datetime, timezone

from stock_watchlist.models import Quote, QuoteError, WatchlistItem
from stock_watchlist.pulse import build_market_pulse


class StubProvider:
    def __init__(self, quotes: dict[str, Quote], errors: dict[str, str] | None = None) -> None:
        self._quotes = quotes
        self._errors = errors or {}

    def fetch_quotes(self, symbols: list[str]) -> tuple[list[Quote], list[QuoteError]]:
        found = [self._quotes[s] for s in symbols if s in self._quotes]
        errs = [QuoteError(symbol=s, error=self._errors[s]) for s in symbols if s in self._errors]
        return found, errs


def _quote(symbol: str, price: float, pct: float, currency: str = "USD") -> Quote:
    return Quote(
        symbol=symbol,
        name=symbol,
        currency=currency,
        exchange="NMS",
        market_state="REGULAR",
        price=price,
        previous_close=price / (1 + pct / 100.0),
        change=round(price - price / (1 + pct / 100.0), 2),
        change_percent=pct,
        five_day_change_percent=pct * 2,
        timestamp="2026-11-26T00:00:00+00:00",
    )


def test_build_market_pulse_computes_summary_and_alerts() -> None:
    items = [
        WatchlistItem(
            symbol="BBCA.JK",
            name="Bank Central Asia",
            market="IDX",
            buy_below=9000.0,
            note="Accumulate zone",
        ),
        WatchlistItem(symbol="NVDA", name="NVIDIA", market="US", sell_above=140.0),
        WatchlistItem(symbol="AAPL", name="Apple", market="US"),
    ]
    provider = StubProvider(
        quotes={
            "^JKSE": _quote("^JKSE", 7300.0, 0.5, currency="IDR"),
            "BBCA.JK": _quote("BBCA.JK", 8950.0, -1.2, currency="IDR"),
            "NVDA": _quote("NVDA", 142.5, 4.2, currency="USD"),
            "AAPL": _quote("AAPL", 220.0, 0.0, currency="USD"),
        }
    )

    report = build_market_pulse(
        items,
        provider,
        benchmarks=["^JKSE"],
        now=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc),
    )

    assert len(report.benchmarks) == 1
    assert [q.symbol for q in report.quotes] == ["BBCA.JK", "NVDA", "AAPL"]
    # Alias applied when Yahoo returned raw symbol as name
    assert report.quotes[0].name == "Bank Central Asia"

    assert report.summary.total == 3
    assert report.summary.up == 1
    assert report.summary.down == 1
    assert report.summary.flat == 1
    assert report.summary.avg_change_percent == 1.0
    assert [q.symbol for q in report.summary.top_gainers] == ["NVDA"]
    assert [q.symbol for q in report.summary.top_losers] == ["BBCA.JK"]

    assert len(report.alerts) == 2
    assert report.alerts[0].symbol == "BBCA.JK"
    assert report.alerts[0].kind == "BUY_TARGET"
    assert report.alerts[1].symbol == "NVDA"
    assert report.alerts[1].kind == "SELL_TARGET"
