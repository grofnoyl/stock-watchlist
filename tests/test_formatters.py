"""Tests for Markdown, JSON, and text output formatters."""

from __future__ import annotations

import json

from stock_watchlist.formatters import (
    format_percent,
    format_price,
    format_pulse_json,
    format_pulse_markdown,
    format_pulse_text,
    format_volume,
)
from stock_watchlist.models import AlertSignal, MarketPulseReport, PulseSummary, Quote


def _sample_report() -> MarketPulseReport:
    bbca = Quote(
        symbol="BBCA.JK",
        name="Bank Central Asia",
        currency="IDR",
        exchange="JKT",
        market_state="CLOSED",
        price=8950.0,
        previous_close=9050.0,
        change=-100.0,
        change_percent=-1.1,
        day_high=9050.0,
        day_low=8900.0,
        volume=54_200_000,
        five_day_change_percent=-2.5,
        timestamp="2026-11-26T09:00:00+00:00",
    )
    nvda = Quote(
        symbol="NVDA",
        name="NVIDIA",
        currency="USD",
        exchange="NMS",
        market_state="REGULAR",
        price=145.25,
        previous_close=140.0,
        change=5.25,
        change_percent=3.75,
        day_high=146.0,
        day_low=141.0,
        volume=120_000_000,
        five_day_change_percent=6.1,
        timestamp="2026-11-26T09:00:00+00:00",
    )
    alert = AlertSignal(
        symbol="BBCA.JK",
        kind="BUY_TARGET",
        price=8950.0,
        threshold=9000.0,
        currency="IDR",
        note="Core bank",
    )
    return MarketPulseReport(
        generated_at="2026-11-26T09:00:00+00:00",
        benchmarks=[],
        quotes=[bbca, nvda],
        alerts=[alert],
        errors=[],
        summary=PulseSummary(
            total=2,
            up=1,
            down=1,
            flat=0,
            avg_change_percent=1.32,
            top_gainers=[nvda],
            top_losers=[bbca],
        ),
    )


def test_scalar_formatters() -> None:
    assert format_price(9850.0, "IDR") == "Rp 9,850"
    assert format_price(145.25, "USD") == "$145.25"
    assert format_percent(2.5) == "+2.50%"
    assert format_percent(-1.1) == "-1.10%"
    assert format_percent(None) == "—"
    assert format_volume(1_250_000_000) == "1.25B"
    assert format_volume(54_200_000) == "54.20M"
    assert format_volume(3_500) == "3.5K"


def test_pulse_formatters_markdown_json_text() -> None:
    report = _sample_report()

    md = format_pulse_markdown(report)
    assert "# Market Pulse" in md
    assert "Rp 8,950" in md
    assert "$145.25" in md
    assert "BUY_TARGET" in md
    assert "Top Gainers" in md

    md_alerts_only = format_pulse_markdown(report, only_alerts=True)
    assert "BUY_TARGET" in md_alerts_only
    assert "## Watchlist" not in md_alerts_only

    parsed = json.loads(format_pulse_json(report))
    assert parsed["summary"]["total"] == 2
    assert parsed["alerts"][0]["symbol"] == "BBCA.JK"

    txt = format_pulse_text(report)
    assert "MARKET PULSE" in txt
    assert "BBCA.JK" in txt
    assert "SUMMARY: 1 up / 1 down / 0 flat" in txt
