from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BotState(str, Enum):
    ACTIVE = "ACTIVE"    # Claude may trade
    PAUSED = "PAUSED"    # Claude may observe and log, but not trade
    STOPPED = "STOPPED"  # kill switch: positions flattened, trading halted


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class Alert(BaseModel):
    """Generic, indicator-agnostic TradingView alert payload (Phase 1.2)."""

    timestamp: str = Field(default_factory=utcnow_iso)
    symbol: str
    timeframe: str = ""
    indicator: str = "unknown"
    signal: str = "unknown"
    direction: str = "neutral"  # long / short / neutral
    price: Optional[float] = None
    extra: dict[str, Any] = Field(default_factory=dict)
    received_at: str = Field(default_factory=utcnow_iso)


class Position(BaseModel):
    id: str
    symbol: str
    direction: Direction
    size: int
    entry_price: float
    stop: float
    initial_stop: float
    target: Optional[float] = None
    opened_at: str = Field(default_factory=utcnow_iso)
    reasoning: str


class ClosedTrade(BaseModel):
    id: str
    symbol: str
    direction: Direction
    size: int
    entry_price: float
    initial_stop: float
    stop: float
    target: Optional[float] = None
    opened_at: str
    entry_reasoning: str
    exit_price: float
    pnl: float
    r_multiple: Optional[float] = None
    closed_at: str = Field(default_factory=utcnow_iso)
    exit_reasoning: str
