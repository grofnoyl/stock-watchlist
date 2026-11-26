"""Tests for Yahoo Finance v8 Chart API parsing and client fallback."""

from __future__ import annotations

import json
import urllib.error

import pytest

from stock_watchlist.yahoo import YahooFinanceClient, YahooFinanceError, parse_chart_payload


def _make_chart_payload(
    *,
    symbol: str,
    short_name: str,
    currency: str,
    price: float,
    chart_prev_close: float,
    closes: list[float | None],
    previous_close: float | None = None,
    day_high: float | None = None,
    day_low: float | None = None,
    volume: int | None = None,
) -> dict:
    meta: dict = {
        "symbol": symbol,
        "shortName": short_name,
        "currency": currency,
        "exchangeName": "JKT" if symbol.endswith(".JK") else "NMS",
        "marketState": "REGULAR",
        "regularMarketPrice": price,
        "chartPreviousClose": chart_prev_close,
        "regularMarketTime": 1764000000,
    }
    if previous_close is not None:
        meta["previousClose"] = previous_close
    if day_high is not None:
        meta["regularMarketDayHigh"] = day_high
    if day_low is not None:
        meta["regularMarketDayLow"] = day_low
    if volume is not None:
        meta["regularMarketVolume"] = volume

    return {
        "chart": {
            "result": [
                {
                    "meta": meta,
                    "indicators": {"quote": [{"close": closes}]},
                }
            ],
            "error": None,
        }
    }


def test_parse_idx_quote_separates_1d_and_5d_changes() -> None:
    # chartPreviousClose is 5 days ago (9500); yesterday's close is closes[-2] (9800); current is 10000.
    payload = _make_chart_payload(
        symbol="BBCA.JK",
        short_name="Bank Central Asia Tbk",
        currency="IDR",
        price=10000.0,
        chart_prev_close=9500.0,
        closes=[9600.0, 9700.0, 9750.0, 9800.0, 10000.0],
        day_high=10050.0,
        day_low=9850.0,
        volume=65_400_000,
    )

    quote = parse_chart_payload("BBCA.JK", payload)

    assert quote.symbol == "BBCA.JK"
    assert quote.currency == "IDR"
    assert quote.market == "IDX"
    assert quote.price == 10000.0
    assert quote.previous_close == 9800.0
    assert quote.change == 200.0
    assert quote.change_percent == 2.04
    assert quote.five_day_change_percent == 5.26
    assert quote.volume == 65_400_000


def test_parse_quote_prefers_explicit_previous_close() -> None:
    payload = _make_chart_payload(
        symbol="NVDA",
        short_name="NVIDIA Corporation",
        currency="USD",
        price=140.0,
        chart_prev_close=130.0,
        previous_close=135.0,
        closes=[131.0, 133.0, 134.0, 136.0, 140.0],
    )

    quote = parse_chart_payload("nvda", payload)

    assert quote.symbol == "NVDA"
    assert quote.previous_close == 135.0
    assert quote.change == 5.0
    assert quote.change_percent == 3.7
    assert quote.five_day_change_percent == 7.69


def test_parse_chart_error_raises() -> None:
    with pytest.raises(YahooFinanceError, match="No data found"):
        parse_chart_payload(
            "INVALID",
            {"chart": {"result": None, "error": {"description": "No data found"}}},
        )


def test_client_falls_back_to_query2_on_transient_error() -> None:
    calls: list[str] = []

    def fake_get(url: str, timeout: float) -> bytes:
        calls.append(url)
        if "query1.finance.yahoo.com" in url:
            raise urllib.error.URLError("temporary failure")
        payload = _make_chart_payload(
            symbol="AAPL",
            short_name="Apple Inc.",
            currency="USD",
            price=220.0,
            chart_prev_close=210.0,
            previous_close=215.0,
            closes=[212.0, 215.0, 220.0],
        )
        return json.dumps(payload).encode("utf-8")

    client = YahooFinanceClient(http_get=fake_get)
    quote = client.fetch_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert len(calls) == 2
    assert "query1.finance.yahoo.com" in calls[0]
    assert "query2.finance.yahoo.com" in calls[1]


def test_fetch_quotes_preserves_order_and_collects_errors() -> None:
    def fake_get(url: str, timeout: float) -> bytes:
        if "BADTICKER" in url:
            return json.dumps(
                {"chart": {"result": None, "error": {"description": "Symbol not found"}}}
            ).encode("utf-8")
        sym = "BBCA.JK" if "BBCA.JK" in url else "NVDA"
        payload = _make_chart_payload(
            symbol=sym,
            short_name=sym,
            currency="IDR" if sym.endswith(".JK") else "USD",
            price=100.0,
            chart_prev_close=95.0,
            previous_close=98.0,
            closes=[98.0, 100.0],
        )
        return json.dumps(payload).encode("utf-8")

    client = YahooFinanceClient(http_get=fake_get, max_workers=3)
    quotes, errors = client.fetch_quotes(["NVDA", "BADTICKER", "BBCA.JK", "nvda"])

    assert [q.symbol for q in quotes] == ["NVDA", "BBCA.JK"]
    assert len(errors) == 1
    assert errors[0].symbol == "BADTICKER"
