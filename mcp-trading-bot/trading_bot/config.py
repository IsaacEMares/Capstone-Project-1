from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_POINT_VALUES: dict[str, float] = {
    # $ per 1.0 point of price movement, per contract
    "MES": 5.0,
    "MNQ": 2.0,
    "ES": 50.0,
    "NQ": 20.0,
    "M2K": 5.0,
    "MYM": 0.5,
}


def _parse_point_values(raw: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        symbol, _, value = pair.partition("=")
        values[symbol.strip().upper()] = float(value)
    return values


@dataclass
class Settings:
    data_dir: Path
    webhook_secret: str = ""
    api_key: str = ""
    start_balance: float = 50_000.0
    symbol_whitelist: list[str] = field(default_factory=lambda: ["MES", "MNQ"])
    max_position_size: int = 10
    point_values: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_POINT_VALUES))

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(
            os.environ.get("BOT_DATA_DIR", Path(__file__).resolve().parent.parent / "data")
        )
        point_values = dict(DEFAULT_POINT_VALUES)
        point_values.update(_parse_point_values(os.environ.get("SYMBOL_POINT_VALUES", "")))
        whitelist = [
            s.strip().upper()
            for s in os.environ.get("SYMBOL_WHITELIST", "MES,MNQ").split(",")
            if s.strip()
        ]
        return cls(
            data_dir=data_dir,
            webhook_secret=os.environ.get("WEBHOOK_SECRET", ""),
            api_key=os.environ.get("BOT_API_KEY", ""),
            start_balance=float(os.environ.get("ACCOUNT_START_BALANCE", "50000")),
            symbol_whitelist=whitelist,
            max_position_size=int(os.environ.get("MAX_POSITION_SIZE", "10")),
            point_values=point_values,
        )

    def point_value(self, symbol: str) -> float:
        return self.point_values.get(symbol.upper(), 1.0)
