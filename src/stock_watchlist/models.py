"""Data models for stock-watchlist."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def infer_market(symbol: str) -> str:
    """Infer market classification from a normalized ticker symbol."""
    upper = symbol.strip().upper()
    if upper.endswith(".JK"):
        return "IDX"
    if upper.startswith("^"):
        return "INDEX"
    if upper.endswith("=X"):
        return "FX"
    return "US"


def normalize_symbol(symbol: str, *, idx: bool = False) -> str:
    """Normalize ticker casing and optionally apply the IDX `.JK` suffix."""
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("Ticker symbol cannot be empty.")
    if idx and "." not in cleaned and not cleaned.startswith("^") and "=" not in cleaned:
        return f"{cleaned}.JK"
    return cleaned


@dataclass(slots=True)
class WatchlistItem:
    """A single tracked ticker and optional alert thresholds."""

    symbol: str
    name: str | None = None
    market: str = "US"
    buy_below: float | None = None
    sell_above: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        self.symbol = normalize_symbol(self.symbol)
        if not self.market:
            self.market = infer_market(self.symbol)
        else:
            self.market = self.market.upper()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatchlistItem:
        symbol = normalize_symbol(str(data["symbol"]))
        market = str(data.get("market") or infer_market(symbol)).upper()
        buy_below = data.get("buy_below")
        sell_above = data.get("sell_above")
        return cls(
            symbol=symbol,
            name=data.get("name") or None,
            market=market,
            buy_below=float(buy_below) if buy_below is not None else None,
            sell_above=float(sell_above) if sell_above is not None else None,
            note=str(data.get("note") or ""),
        )


@dataclass(slots=True)
class WatchlistConfig:
    """Persistent watchlist configuration containing benchmarks and tracked stocks."""

    items: list[WatchlistItem] = field(default_factory=list)
    benchmarks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmarks": list(self.benchmarks),
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(slots=True)
class Quote:
    """Normalized stock/index quote from Yahoo Finance."""

    symbol: str
    name: str
    currency: str
    exchange: str
    market_state: str
    price: float
    previous_close: float
    change: float
    change_percent: float
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None
    five_day_change_percent: float | None = None
    timestamp: str = ""

    @property
    def market(self) -> str:
        return infer_market(self.symbol)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["market"] = self.market
        return payload


@dataclass(slots=True)
class AlertSignal:
    """Triggered buy/sell price threshold alert."""

    symbol: str
    kind: str  # "BUY_TARGET" or "SELL_TARGET"
    price: float
    threshold: float
    currency: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QuoteError:
    """Error recorded when a symbol quote could not be fetched."""

    symbol: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PulseSummary:
    """Aggregate statistics across fetched watchlist quotes."""

    total: int
    up: int
    down: int
    flat: int
    avg_change_percent: float | None
    top_gainers: list[Quote] = field(default_factory=list)
    top_losers: list[Quote] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "up": self.up,
            "down": self.down,
            "flat": self.flat,
            "avg_change_percent": self.avg_change_percent,
            "top_gainers": [q.to_dict() for q in self.top_gainers],
            "top_losers": [q.to_dict() for q in self.top_losers],
        }


@dataclass(slots=True)
class MarketPulseReport:
    """Complete Market Pulse output model."""

    generated_at: str
    benchmarks: list[Quote]
    quotes: list[Quote]
    alerts: list[AlertSignal]
    errors: list[QuoteError]
    summary: PulseSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "benchmarks": [q.to_dict() for q in self.benchmarks],
            "quotes": [q.to_dict() for q in self.quotes],
            "alerts": [a.to_dict() for a in self.alerts],
            "errors": [e.to_dict() for e in self.errors],
            "summary": self.summary.to_dict(),
        }
