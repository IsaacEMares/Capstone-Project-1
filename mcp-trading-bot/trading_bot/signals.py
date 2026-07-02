from __future__ import annotations

import json
from pathlib import Path

from .models import Alert

DEFAULT_DEFINITIONS = {
    "_comment": (
        "Signal definitions (Phase 2 living document). Keys are signal names as sent "
        "in the TradingView alert 'signal' field; values describe what the signal means. "
        "Signals NOT listed here are observe/log only — Claude must never trade on them."
    ),
}


class SignalStore:
    """Stores incoming alerts (JSONL) and price ticks, indicator-agnostic (Phase 1.2)."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.signals_path = data_dir / "signals.jsonl"
        self.ticks_path = data_dir / "ticks.jsonl"
        self.definitions_path = data_dir / "signal_definitions.json"
        data_dir.mkdir(parents=True, exist_ok=True)
        if not self.definitions_path.exists():
            self.definitions_path.write_text(json.dumps(DEFAULT_DEFINITIONS, indent=2))

    def defined_signals(self) -> dict[str, str]:
        try:
            raw = json.loads(self.definitions_path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        return {k: v for k, v in raw.items() if not k.startswith("_")}

    def add(self, alert: Alert) -> dict:
        record = alert.model_dump()
        record["defined"] = alert.signal in self.defined_signals()
        with self.signals_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        if alert.price is not None:
            self.add_tick(alert.symbol, alert.price, alert.received_at)
        return record

    def add_tick(self, symbol: str, price: float, ts: str) -> None:
        with self.ticks_path.open("a") as f:
            f.write(json.dumps({"symbol": symbol.upper(), "price": price, "ts": ts}) + "\n")

    def recent(self, limit: int = 20) -> list[dict]:
        records = self._read_jsonl(self.signals_path)
        defined = self.defined_signals()
        out = []
        for r in records[-limit:]:
            r["defined"] = r.get("signal") in defined
            if not r["defined"]:
                r["note"] = "UNDEFINED signal — observe and log only, do NOT trade on this"
            out.append(r)
        return list(reversed(out))

    def candles(self, symbol: str, timeframe_minutes: int, bars: int) -> list[dict]:
        """Aggregate stored ticks into OHLC candles.

        This is a stopgap price feed built from webhook ticks; a real market
        data provider can replace it later without changing the MCP tools.
        """
        symbol = symbol.upper()
        ticks = [t for t in self._read_jsonl(self.ticks_path) if t["symbol"] == symbol]
        buckets: dict[int, dict] = {}
        width = timeframe_minutes * 60
        from datetime import datetime

        for t in ticks:
            try:
                epoch = int(datetime.fromisoformat(t["ts"]).timestamp())
            except ValueError:
                continue
            key = epoch - (epoch % width)
            candle = buckets.get(key)
            price = t["price"]
            if candle is None:
                buckets[key] = {
                    "time": datetime.fromtimestamp(key).isoformat(),
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "ticks": 1,
                }
            else:
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price
                candle["ticks"] += 1
        return [buckets[k] for k in sorted(buckets)][-bars:]

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records
