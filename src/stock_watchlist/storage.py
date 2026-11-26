"""JSON storage for watchlist configuration with atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import WatchlistConfig, WatchlistItem, infer_market, normalize_symbol

DEFAULT_BENCHMARKS: list[str] = ["^JKSE", "^GSPC", "^IXIC", "USDIDR=X"]

PRESET_ITEMS: dict[str, list[WatchlistItem]] = {
    "idx": [
        WatchlistItem(symbol="BBCA.JK", name="Bank Central Asia", market="IDX"),
        WatchlistItem(symbol="BBRI.JK", name="Bank Rakyat Indonesia", market="IDX"),
        WatchlistItem(symbol="BMRI.JK", name="Bank Mandiri", market="IDX"),
        WatchlistItem(symbol="TLKM.JK", name="Telkom Indonesia", market="IDX"),
    ],
    "us": [
        WatchlistItem(symbol="NVDA", name="NVIDIA", market="US"),
        WatchlistItem(symbol="AAPL", name="Apple", market="US"),
        WatchlistItem(symbol="MSFT", name="Microsoft", market="US"),
    ],
}


def resolve_watchlist_path(explicit_path: str | Path | None = None) -> Path:
    """Resolve the watchlist JSON path using CLI flag, env var, cwd, or XDG config."""
    if explicit_path is not None:
        return Path(explicit_path).expanduser()

    env_path = os.environ.get("STOCK_WATCHLIST_FILE")
    if env_path:
        return Path(env_path).expanduser()

    local_file = Path.cwd() / "watchlist.json"
    if local_file.exists():
        return local_file

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    base_dir = Path(xdg_config).expanduser() if xdg_config else Path.home() / ".config"
    return base_dir / "stock-watchlist" / "watchlist.json"


def default_config(preset: str = "all") -> WatchlistConfig:
    """Build a starter watchlist configuration for IDX, US, or both."""
    preset_key = preset.lower()
    if preset_key == "idx":
        items = [WatchlistItem.from_dict(i.to_dict()) for i in PRESET_ITEMS["idx"]]
        benchmarks = ["^JKSE", "USDIDR=X"]
    elif preset_key == "us":
        items = [WatchlistItem.from_dict(i.to_dict()) for i in PRESET_ITEMS["us"]]
        benchmarks = ["^GSPC", "^IXIC"]
    elif preset_key == "all":
        items = [
            WatchlistItem.from_dict(i.to_dict())
            for i in (*PRESET_ITEMS["idx"], *PRESET_ITEMS["us"])
        ]
        benchmarks = list(DEFAULT_BENCHMARKS)
    else:
        raise ValueError(f"Unknown preset '{preset}'. Expected one of: all, idx, us.")
    return WatchlistConfig(items=items, benchmarks=benchmarks)


def load_watchlist(path: Path) -> WatchlistConfig:
    """Load watchlist configuration from JSON file, returning empty config if missing."""
    if not path.exists():
        return WatchlistConfig(items=[], benchmarks=list(DEFAULT_BENCHMARKS))

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid watchlist format in {path}: expected JSON object.")

    raw_benchmarks = raw.get("benchmarks")
    if isinstance(raw_benchmarks, list):
        benchmarks = [normalize_symbol(str(s)) for s in raw_benchmarks if str(s).strip()]
    else:
        benchmarks = list(DEFAULT_BENCHMARKS)

    raw_items = raw.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError(f"Invalid 'items' field in {path}: expected list.")

    items: list[WatchlistItem] = []
    seen: set[str] = set()
    for entry in raw_items:
        if isinstance(entry, str):
            sym = normalize_symbol(entry)
            item = WatchlistItem(symbol=sym, market=infer_market(sym))
        elif isinstance(entry, dict):
            item = WatchlistItem.from_dict(entry)
        else:
            continue
        if item.symbol not in seen:
            seen.add(item.symbol)
            items.append(item)

    return WatchlistConfig(items=items, benchmarks=benchmarks)


def save_watchlist(path: Path, config: WatchlistConfig) -> None:
    """Atomically write watchlist JSON configuration to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".watchlist.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def upsert_item(
    config: WatchlistConfig,
    symbol: str,
    *,
    idx: bool = False,
    name: str | None = None,
    buy_below: float | None = None,
    sell_above: float | None = None,
    note: str | None = None,
) -> tuple[WatchlistItem, bool]:
    """Insert or update a watchlist item. Returns (item, created)."""
    normalized = normalize_symbol(symbol, idx=idx)
    market = infer_market(normalized)

    for existing in config.items:
        if existing.symbol == normalized:
            if name is not None:
                existing.name = name or None
            if buy_below is not None:
                existing.buy_below = buy_below
            if sell_above is not None:
                existing.sell_above = sell_above
            if note is not None:
                existing.note = note
            existing.market = market
            return existing, False

    item = WatchlistItem(
        symbol=normalized,
        name=name or None,
        market=market,
        buy_below=buy_below,
        sell_above=sell_above,
        note=note or "",
    )
    config.items.append(item)
    return item, True


def remove_item(config: WatchlistConfig, symbol: str, *, idx: bool = False) -> bool:
    """Remove a symbol from watchlist config. Returns True if removed."""
    normalized = normalize_symbol(symbol, idx=idx)
    original_len = len(config.items)
    config.items = [item for item in config.items if item.symbol != normalized]
    return len(config.items) < original_len
