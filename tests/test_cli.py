"""End-to-end CLI tests with deterministic quote provider."""

from __future__ import annotations

import json
from pathlib import Path

from stock_watchlist.cli import main
from stock_watchlist.models import Quote, QuoteError


class FakeProvider:
    def fetch_quotes(self, symbols: list[str]) -> tuple[list[Quote], list[QuoteError]]:
        quotes: list[Quote] = []
        errors: list[QuoteError] = []
        for sym in symbols:
            if sym == "ERR":
                errors.append(QuoteError(symbol=sym, error="Not found"))
                continue
            is_idr = sym.endswith(".JK") or sym == "^JKSE"
            price = 8800.0 if sym == "BBCA.JK" else 145.0
            quotes.append(
                Quote(
                    symbol=sym,
                    name=f"{sym} Corp",
                    currency="IDR" if is_idr else "USD",
                    exchange="JKT" if is_idr else "NMS",
                    market_state="REGULAR",
                    price=price,
                    previous_close=price * 0.99,
                    change=round(price * 0.01, 2),
                    change_percent=1.01,
                    five_day_change_percent=2.5,
                    volume=10_000_000,
                    timestamp="2026-11-26T00:00:00+00:00",
                )
            )
        return quotes, errors


def test_cli_init_add_list_remove(tmp_path: Path, capsys) -> None:
    wl = tmp_path / "watchlist.json"

    assert main(["-f", str(wl), "init", "--preset", "idx"]) == 0
    assert "Initialized watchlist" in capsys.readouterr().out

    # Second init without --force fails
    assert main(["-f", str(wl), "init"]) == 1
    capsys.readouterr()

    assert main(["-f", str(wl), "add", "nvda", "--name", "NVIDIA", "--sell-above", "140"]) == 0
    assert "Added NVDA (US)" in capsys.readouterr().out

    assert main(["-f", str(wl), "list", "--market", "us", "--format", "json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [i["symbol"] for i in listed] == ["NVDA"]

    assert main(["-f", str(wl), "remove", "nvda"]) == 0
    assert "Removed NVDA" in capsys.readouterr().out


def test_cli_pulse_json_and_exit_on_alert(tmp_path: Path, capsys) -> None:
    wl = tmp_path / "watchlist.json"
    provider = FakeProvider()

    assert main(["-f", str(wl), "add", "BBCA", "--idx", "--buy-below", "9000"]) == 0
    capsys.readouterr()

    code = main(
        ["-f", str(wl), "pulse", "--format", "json", "--no-benchmarks", "--exit-on-alert"],
        provider=provider,
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["alerts"][0]["symbol"] == "BBCA.JK"
    assert payload["alerts"][0]["kind"] == "BUY_TARGET"


def test_cli_quote_idx_shorthand(capsys) -> None:
    provider = FakeProvider()
    code = main(["quote", "bbca", "--idx", "--format", "text"], provider=provider)
    assert code == 0
    out = capsys.readouterr().out
    assert "BBCA.JK" in out
    assert "Rp 8,800" in out
