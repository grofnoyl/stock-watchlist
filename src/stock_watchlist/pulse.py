"""Market Pulse analytics, breadth summary, and alert evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from .models import (
    AlertSignal,
    MarketPulseReport,
    PulseSummary,
    Quote,
    QuoteError,
    WatchlistItem,
)


class QuoteProvider(Protocol):
    """Protocol implemented by YahooFinanceClient and test doubles."""

    def fetch_quotes(self, symbols: list[str]) -> tuple[list[Quote], list[QuoteError]]:
        ...


def evaluate_alerts(items: list[WatchlistItem], quotes: list[Quote]) -> list[AlertSignal]:
    """Check watchlist quotes against buy_below and sell_above thresholds."""
    by_symbol = {quote.symbol: quote for quote in quotes}
    alerts: list[AlertSignal] = []

    for item in items:
        quote = by_symbol.get(item.symbol)
        if quote is None:
            continue
        if item.buy_below is not None and quote.price <= item.buy_below:
            alerts.append(
                AlertSignal(
                    symbol=item.symbol,
                    kind="BUY_TARGET",
                    price=quote.price,
                    threshold=item.buy_below,
                    currency=quote.currency,
                    note=item.note,
                )
            )
        if item.sell_above is not None and quote.price >= item.sell_above:
            alerts.append(
                AlertSignal(
                    symbol=item.symbol,
                    kind="SELL_TARGET",
                    price=quote.price,
                    threshold=item.sell_above,
                    currency=quote.currency,
                    note=item.note,
                )
            )

    return alerts


def compute_summary(quotes: list[Quote], *, top_n: int = 3) -> PulseSummary:
    """Compute breadth (up/down/flat), average change, and top movers."""
    total = len(quotes)
    if total == 0:
        return PulseSummary(
            total=0,
            up=0,
            down=0,
            flat=0,
            avg_change_percent=None,
            top_gainers=[],
            top_losers=[],
        )

    up = sum(1 for q in quotes if q.change_percent > 0)
    down = sum(1 for q in quotes if q.change_percent < 0)
    flat = total - up - down
    avg_change = round(sum(q.change_percent for q in quotes) / total, 2)

    gainers = sorted(
        (q for q in quotes if q.change_percent > 0),
        key=lambda q: (-q.change_percent, q.symbol),
    )[:top_n]
    losers = sorted(
        (q for q in quotes if q.change_percent < 0),
        key=lambda q: (q.change_percent, q.symbol),
    )[:top_n]

    return PulseSummary(
        total=total,
        up=up,
        down=down,
        flat=flat,
        avg_change_percent=avg_change,
        top_gainers=gainers,
        top_losers=losers,
    )


def build_market_pulse(
    items: list[WatchlistItem],
    provider: QuoteProvider,
    *,
    benchmarks: list[str] | None = None,
    include_benchmarks: bool = True,
    now: datetime | None = None,
) -> MarketPulseReport:
    """Fetch quotes for benchmarks and watchlist items and compile a MarketPulseReport."""
    benchmark_symbols = list(benchmarks or []) if include_benchmarks else []
    item_symbols = [item.symbol for item in items]

    all_symbols: list[str] = []
    for sym in (*benchmark_symbols, *item_symbols):
        if sym not in all_symbols:
            all_symbols.append(sym)

    fetched_quotes, errors = provider.fetch_quotes(all_symbols)
    quote_map = {q.symbol: q for q in fetched_quotes}

    # Prefer custom user alias only if Yahoo returned the raw symbol as name.
    alias_map = {item.symbol: item.name for item in items if item.name}

    benchmark_quotes = [quote_map[s] for s in benchmark_symbols if s in quote_map]
    watchlist_quotes: list[Quote] = []
    for sym in item_symbols:
        quote = quote_map.get(sym)
        if quote is None:
            continue
        if quote.name == quote.symbol and sym in alias_map:
            quote.name = alias_map[sym] or quote.name
        watchlist_quotes.append(quote)

    alerts = evaluate_alerts(items, watchlist_quotes)
    summary = compute_summary(watchlist_quotes)
    generated_at = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc).isoformat()

    return MarketPulseReport(
        generated_at=generated_at,
        benchmarks=benchmark_quotes,
        quotes=watchlist_quotes,
        alerts=alerts,
        errors=errors,
        summary=summary,
    )
