"""Output formatters (Markdown, JSON, compact text) for Hermes Agent & CLI."""

from __future__ import annotations

import json

from .models import AlertSignal, MarketPulseReport, Quote, QuoteError, WatchlistItem


def format_price(value: float, currency: str) -> str:
    """Format a price with currency-aware precision (IDR vs USD vs index)."""
    curr = currency.upper()
    if curr == "IDR":
        if abs(value - round(value)) < 1e-6:
            return f"Rp {value:,.0f}"
        return f"Rp {value:,.2f}"
    if curr == "USD":
        return f"${value:,.2f}"
    return f"{value:,.2f} {curr}".strip()


def format_percent(value: float | None) -> str:
    """Format signed percentage value."""
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def format_volume(volume: int | None) -> str:
    """Compact human-readable volume."""
    if volume is None:
        return "—"
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.2f}B"
    if volume >= 1_000_000:
        return f"{volume / 1_000_000:.2f}M"
    if volume >= 1_000:
        return f"{volume / 1_000:.1f}K"
    return str(volume)


def _trend_badge(change_percent: float) -> str:
    if change_percent > 0:
        return "▲"
    if change_percent < 0:
        return "▼"
    return "•"


def format_pulse_json(report: MarketPulseReport) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def format_pulse_markdown(report: MarketPulseReport, *, only_alerts: bool = False) -> str:
    lines: list[str] = [
        f"# Market Pulse ({report.generated_at})",
        "",
    ]

    if report.alerts:
        lines.append("## Triggered Alerts")
        for alert in report.alerts:
            lines.append(_format_alert_md(alert))
        lines.append("")
    elif only_alerts:
        lines.append("_No price alerts triggered._")
        return "\n".join(lines)

    if only_alerts:
        return "\n".join(lines).rstrip()

    if report.benchmarks:
        lines.extend(
            [
                "## Market Benchmarks",
                "| Symbol | Name | Price | 1D % | 5D % |",
                "| :--- | :--- | ---: | ---: | ---: |",
            ]
        )
        for q in report.benchmarks:
            badge = _trend_badge(q.change_percent)
            lines.append(
                f"| `{q.symbol}` | {q.name} | {format_price(q.price, q.currency)} "
                f"| {badge} {format_percent(q.change_percent)} "
                f"| {format_percent(q.five_day_change_percent)} |"
            )
        lines.append("")

    if report.quotes:
        lines.extend(
            [
                "## Watchlist",
                "| Ticker | Name | Price | 1D % | 5D % | Day Range | Vol |",
                "| :--- | :--- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for q in report.quotes:
            badge = _trend_badge(q.change_percent)
            day_range = (
                f"{format_price(q.day_low, q.currency)}–{format_price(q.day_high, q.currency)}"
                if q.day_low is not None and q.day_high is not None
                else "—"
            )
            lines.append(
                f"| `{q.symbol}` | {q.name} | {format_price(q.price, q.currency)} "
                f"| {badge} {format_percent(q.change_percent)} "
                f"| {format_percent(q.five_day_change_percent)} "
                f"| {day_range} | {format_volume(q.volume)} |"
            )
        lines.append("")

        summary = report.summary
        lines.append("## Summary")
        lines.append(
            f"- **Breadth:** {summary.up} up / {summary.down} down / {summary.flat} flat "
            f"(total {summary.total})"
        )
        lines.append(f"- **Avg 1D Move:** {format_percent(summary.avg_change_percent)}")
        if summary.top_gainers:
            gainers = ", ".join(
                f"`{q.symbol}` ({format_percent(q.change_percent)})" for q in summary.top_gainers
            )
            lines.append(f"- **Top Gainers:** {gainers}")
        if summary.top_losers:
            losers = ", ".join(
                f"`{q.symbol}` ({format_percent(q.change_percent)})" for q in summary.top_losers
            )
            lines.append(f"- **Top Losers:** {losers}")
        lines.append("")
    else:
        lines.append("_No watchlist quotes available._")
        lines.append("")

    if report.errors:
        lines.append("## Fetch Errors")
        for err in report.errors:
            lines.append(f"- `{err.symbol}`: {err.error}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_alert_md(alert: AlertSignal) -> str:
    label = "BUY <= " if alert.kind == "BUY_TARGET" else "SELL >= "
    note = f" — {alert.note}" if alert.note else ""
    return (
        f"- **{alert.symbol}** [{alert.kind}]: "
        f"{format_price(alert.price, alert.currency)} "
        f"({label}{format_price(alert.threshold, alert.currency)}){note}"
    )


def format_pulse_text(report: MarketPulseReport, *, only_alerts: bool = False) -> str:
    lines: list[str] = [f"MARKET PULSE @ {report.generated_at}"]

    if report.alerts:
        lines.append("ALERTS:")
        for alert in report.alerts:
            op = "<=" if alert.kind == "BUY_TARGET" else ">="
            lines.append(
                f"  ! {alert.symbol} {alert.kind}: "
                f"{format_price(alert.price, alert.currency)} "
                f"({op} {format_price(alert.threshold, alert.currency)})"
            )
    elif only_alerts:
        lines.append("No alerts triggered.")
        return "\n".join(lines)

    if only_alerts:
        return "\n".join(lines)

    if report.benchmarks:
        lines.append("BENCHMARKS:")
        for q in report.benchmarks:
            lines.append(
                f"  {q.symbol:<10} {format_price(q.price, q.currency):>14} "
                f"{format_percent(q.change_percent):>8} (5D {format_percent(q.five_day_change_percent)})"
            )

    if report.quotes:
        lines.append("WATCHLIST:")
        for q in report.quotes:
            lines.append(
                f"  {q.symbol:<10} {format_price(q.price, q.currency):>14} "
                f"{format_percent(q.change_percent):>8} "
                f"(5D {format_percent(q.five_day_change_percent):>7})  vol={format_volume(q.volume)}"
            )
        s = report.summary
        lines.append(
            f"SUMMARY: {s.up} up / {s.down} down / {s.flat} flat | "
            f"avg 1D {format_percent(s.avg_change_percent)}"
        )

    if report.errors:
        lines.append("ERRORS:")
        for err in report.errors:
            lines.append(f"  x {err.symbol}: {err.error}")

    return "\n".join(lines)


def format_quotes(quotes: list[Quote], errors: list[QuoteError], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(
            {
                "quotes": [q.to_dict() for q in quotes],
                "errors": [e.to_dict() for e in errors],
            },
            indent=2,
            ensure_ascii=False,
        )

    if fmt == "text":
        lines = [
            f"{q.symbol:<10} {format_price(q.price, q.currency):>14} "
            f"{format_percent(q.change_percent):>8} "
            f"(5D {format_percent(q.five_day_change_percent):>7})  {q.name}"
            for q in quotes
        ]
        for err in errors:
            lines.append(f"ERROR {err.symbol}: {err.error}")
        return "\n".join(lines)

    lines: list[str] = []
    if quotes:
        lines.extend(
            [
                "| Ticker | Name | Price | 1D % | 5D % | Vol |",
                "| :--- | :--- | ---: | ---: | ---: | ---: |",
            ]
        )
        for q in quotes:
            badge = _trend_badge(q.change_percent)
            lines.append(
                f"| `{q.symbol}` | {q.name} | {format_price(q.price, q.currency)} "
                f"| {badge} {format_percent(q.change_percent)} "
                f"| {format_percent(q.five_day_change_percent)} | {format_volume(q.volume)} |"
            )
    if errors:
        if lines:
            lines.append("")
        lines.append("**Errors:**")
        for err in errors:
            lines.append(f"- `{err.symbol}`: {err.error}")
    return "\n".join(lines)


def format_watchlist(items: list[WatchlistItem], fmt: str) -> str:
    if fmt == "json":
        return json.dumps([item.to_dict() for item in items], indent=2, ensure_ascii=False)

    if not items:
        return "Watchlist is empty." if fmt == "text" else "_Watchlist is empty._"

    if fmt == "text":
        lines = []
        for item in items:
            targets: list[str] = []
            if item.buy_below is not None:
                targets.append(f"buy<={item.buy_below:g}")
            if item.sell_above is not None:
                targets.append(f"sell>={item.sell_above:g}")
            target_str = f" [{' '.join(targets)}]" if targets else ""
            note_str = f" — {item.note}" if item.note else ""
            lines.append(f"{item.symbol:<10} ({item.market:<5}) {item.name or ''}{target_str}{note_str}".rstrip())
        return "\n".join(lines)

    lines = [
        "| Ticker | Market | Name | Buy <= | Sell >= | Note |",
        "| :--- | :--- | :--- | ---: | ---: | :--- |",
    ]
    for item in items:
        buy = f"{item.buy_below:,.2f}" if item.buy_below is not None else "—"
        sell = f"{item.sell_above:,.2f}" if item.sell_above is not None else "—"
        lines.append(
            f"| `{item.symbol}` | {item.market} | {item.name or '—'} | {buy} | {sell} | {item.note or '—'} |"
        )
    return "\n".join(lines)
