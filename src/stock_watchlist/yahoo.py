"""Zero-dependency Yahoo Finance v8 Chart API client for IDX & US tickers."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from .models import Quote, QuoteError, normalize_symbol

YAHOO_CHART_HOSTS = (
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com",
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

KNOWN_BENCHMARK_NAMES: dict[str, str] = {
    "^JKSE": "IHSG (IDX Composite)",
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq Composite",
    "^DJI": "Dow Jones",
    "USDIDR=X": "USD/IDR",
}


class YahooFinanceError(RuntimeError):
    """Raised when Yahoo Finance returns an invalid or failed response."""


def _default_http_get(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_valid_closes(result: dict[str, Any]) -> list[float]:
    indicators = result.get("indicators") or {}
    quote_series = indicators.get("quote") or []
    if not quote_series or not isinstance(quote_series[0], dict):
        return []
    raw_closes = quote_series[0].get("close") or []
    closes: list[float] = []
    for val in raw_closes:
        parsed = _to_float(val)
        if parsed is not None and parsed > 0:
            closes.append(parsed)
    return closes


def _determine_previous_close(meta: dict[str, Any], closes: list[float], price: float) -> float:
    """Resolve yesterday's close accurately for a `range=5d&interval=1d` chart."""
    for key in ("regularMarketPreviousClose", "previousClose"):
        candidate = _to_float(meta.get(key))
        if candidate is not None and candidate > 0:
            return candidate

    if len(closes) >= 2:
        return closes[-2]

    chart_prev = _to_float(meta.get("chartPreviousClose"))
    if chart_prev is not None and chart_prev > 0:
        return chart_prev

    return closes[0] if closes else price


def parse_chart_payload(requested_symbol: str, payload: dict[str, Any]) -> Quote:
    """Parse Yahoo Finance v8 chart JSON into a normalized Quote."""
    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise YahooFinanceError("Malformed response: missing 'chart' object.")

    err = chart.get("error")
    if err:
        description = err.get("description") if isinstance(err, dict) else str(err)
        raise YahooFinanceError(f"Yahoo Finance error: {description}")

    results = chart.get("result")
    if not results or not isinstance(results, list) or not isinstance(results[0], dict):
        raise YahooFinanceError(f"No quote data returned for '{requested_symbol}'.")

    result = results[0]
    meta = result.get("meta") or {}
    closes = _extract_valid_closes(result)

    price = _to_float(meta.get("regularMarketPrice"))
    if price is None and closes:
        price = closes[-1]
    if price is None:
        raise YahooFinanceError(f"Missing price in response for '{requested_symbol}'.")

    prev_close = _determine_previous_close(meta, closes, price)
    change = price - prev_close
    change_percent = (change / prev_close * 100.0) if prev_close else 0.0

    # 5-day change compares current price to pre-window chartPreviousClose (or first close).
    five_day_base = _to_float(meta.get("chartPreviousClose"))
    if (five_day_base is None or five_day_base <= 0) and closes:
        five_day_base = closes[0]
    five_day_pct: float | None = None
    if five_day_base is not None and five_day_base > 0:
        five_day_pct = round((price - five_day_base) / five_day_base * 100.0, 2)

    symbol = normalize_symbol(str(meta.get("symbol") or requested_symbol))
    name = (
        str(meta.get("shortName") or meta.get("longName") or "").strip()
        or KNOWN_BENCHMARK_NAMES.get(symbol, symbol)
    )
    currency = str(meta.get("currency") or ("IDR" if symbol.endswith(".JK") else "USD")).upper()
    exchange = str(meta.get("exchangeName") or meta.get("fullExchangeName") or "").strip()
    market_state = str(meta.get("marketState") or "UNKNOWN").upper()

    market_time = _to_int(meta.get("regularMarketTime"))
    if market_time:
        timestamp = datetime.fromtimestamp(market_time, tz=timezone.utc).isoformat()
    else:
        timestamp = datetime.now(tz=timezone.utc).isoformat()

    day_high = _to_float(meta.get("regularMarketDayHigh"))
    day_low = _to_float(meta.get("regularMarketDayLow"))
    volume = _to_int(meta.get("regularMarketVolume"))

    return Quote(
        symbol=symbol,
        name=name,
        currency=currency,
        exchange=exchange,
        market_state=market_state,
        price=round(price, 4),
        previous_close=round(prev_close, 4),
        change=round(change, 4),
        change_percent=round(change_percent, 2),
        day_high=round(day_high, 4) if day_high is not None else None,
        day_low=round(day_low, 4) if day_low is not None else None,
        volume=volume,
        five_day_change_percent=five_day_pct,
        timestamp=timestamp,
    )


class YahooFinanceClient:
    """Lightweight HTTP client for Yahoo Finance chart quotes."""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        max_workers: int = 6,
        http_get: Callable[[str, float], bytes] | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_workers = max(1, max_workers)
        self._http_get = http_get or _default_http_get

    def fetch_quote(self, symbol: str) -> Quote:
        """Fetch a single symbol quote, trying query1 then query2 on transient failures."""
        normalized = normalize_symbol(symbol)
        encoded = urllib.parse.quote(normalized, safe="")
        last_error: Exception | None = None

        for host in YAHOO_CHART_HOSTS:
            url = f"{host}/v8/finance/chart/{encoded}?interval=1d&range=5d"
            try:
                raw = self._http_get(url, self.timeout)
                payload = json.loads(raw.decode("utf-8"))
                return parse_chart_payload(normalized, payload)
            except urllib.error.HTTPError as exc:
                last_error = YahooFinanceError(f"HTTP {exc.code}: {exc.reason}")
                if exc.code == 404:
                    break
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = YahooFinanceError(str(exc))
            except YahooFinanceError as exc:
                last_error = exc
                break

        raise YahooFinanceError(str(last_error or f"Failed to fetch quote for {normalized}"))

    def fetch_quotes(self, symbols: list[str]) -> tuple[list[Quote], list[QuoteError]]:
        """Fetch multiple symbols concurrently while preserving input order."""
        deduped: list[str] = []
        seen: set[str] = set()
        for sym in symbols:
            norm = normalize_symbol(sym)
            if norm not in seen:
                seen.add(norm)
                deduped.append(norm)

        if not deduped:
            return [], []

        results: dict[str, Quote] = {}
        errors: dict[str, QuoteError] = {}

        worker_count = min(self.max_workers, len(deduped))
        if worker_count == 1:
            for sym in deduped:
                try:
                    results[sym] = self.fetch_quote(sym)
                except Exception as exc:  # noqa: BLE001
                    errors[sym] = QuoteError(symbol=sym, error=str(exc))
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as pool:
                future_map = {pool.submit(self.fetch_quote, sym): sym for sym in deduped}
                for future in as_completed(future_map):
                    sym = future_map[future]
                    try:
                        results[sym] = future.result()
                    except Exception as exc:  # noqa: BLE001
                        errors[sym] = QuoteError(symbol=sym, error=str(exc))

        ordered_quotes = [results[s] for s in deduped if s in results]
        ordered_errors = [errors[s] for s in deduped if s in errors]
        return ordered_quotes, ordered_errors
