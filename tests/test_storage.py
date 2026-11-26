"""Tests for watchlist JSON persistence and CRUD helpers."""

from __future__ import annotations

from pathlib import Path

from stock_watchlist.storage import (
    default_config,
    load_watchlist,
    remove_item,
    resolve_watchlist_path,
    save_watchlist,
    upsert_item,
)


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "watchlist.json"
    cfg = default_config("all")
    save_watchlist(path, cfg)

    loaded = load_watchlist(path)
    assert [i.symbol for i in loaded.items] == [i.symbol for i in cfg.items]
    assert loaded.benchmarks == cfg.benchmarks


def test_upsert_and_remove_with_idx_flag(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.json"
    cfg = load_watchlist(path)

    item, created = upsert_item(
        cfg,
        "bbca",
        idx=True,
        name="Bank Central Asia",
        buy_below=9000.0,
        note="Core",
    )
    assert created is True
    assert item.symbol == "BBCA.JK"
    assert item.market == "IDX"
    assert item.buy_below == 9000.0

    updated, created_again = upsert_item(cfg, "BBCA.JK", sell_above=11000.0)
    assert created_again is False
    assert updated.buy_below == 9000.0
    assert updated.sell_above == 11000.0
    assert updated.note == "Core"

    assert remove_item(cfg, "bbca", idx=True) is True
    assert remove_item(cfg, "bbca", idx=True) is False
    assert cfg.items == []


def test_resolve_watchlist_path_env_override(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "custom.json"
    monkeypatch.setenv("STOCK_WATCHLIST_FILE", str(target))
    assert resolve_watchlist_path() == target
    assert resolve_watchlist_path(tmp_path / "explicit.json") == tmp_path / "explicit.json"
