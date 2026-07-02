from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Settings
from .models import ClosedTrade, Direction, Position, utcnow_iso


class RejectedOrder(Exception):
    """Raised when an order violates a guardrail. The message says why."""


class PaperAccount:
    """Simulated paper account (Phase 1.3, Option A).

    Fills are simulated against the last known price for a symbol; prices
    arrive as ticks from TradingView webhook alerts. Stops and targets are
    evaluated on every incoming tick.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.path: Path = settings.data_dir / "account.json"
        self.balance: float = settings.start_balance
        self.position: Optional[Position] = None
        self.closed_trades: list[ClosedTrade] = []
        self.last_price: dict[str, float] = {}
        self.daily_pnl: dict[str, float] = {}
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text())
        self.balance = raw["balance"]
        self.position = Position(**raw["position"]) if raw.get("position") else None
        self.closed_trades = [ClosedTrade(**t) for t in raw.get("closed_trades", [])]
        self.last_price = raw.get("last_price", {})
        self.daily_pnl = raw.get("daily_pnl", {})

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "balance": self.balance,
            "position": self.position.model_dump() if self.position else None,
            "closed_trades": [t.model_dump() for t in self.closed_trades],
            "last_price": self.last_price,
            "daily_pnl": self.daily_pnl,
        }
        self.path.write_text(json.dumps(payload, indent=2))

    # ---------- market data ----------

    def on_price(self, symbol: str, price: float) -> Optional[ClosedTrade]:
        """Record a tick; close the open position if its stop/target was hit."""
        symbol = symbol.upper()
        self.last_price[symbol] = price
        closed = None
        pos = self.position
        if pos and pos.symbol == symbol:
            if pos.direction == Direction.LONG:
                if price <= pos.stop:
                    closed = self._close_at(pos.stop, "Stop loss hit.")
                elif pos.target is not None and price >= pos.target:
                    closed = self._close_at(pos.target, "Take-profit target hit.")
            else:
                if price >= pos.stop:
                    closed = self._close_at(pos.stop, "Stop loss hit.")
                elif pos.target is not None and price <= pos.target:
                    closed = self._close_at(pos.target, "Take-profit target hit.")
        self._save()
        return closed

    # ---------- orders ----------

    def enter(
        self,
        direction: str,
        symbol: str,
        size: int,
        stop: float,
        reasoning: str,
        target: Optional[float] = None,
    ) -> Position:
        symbol = symbol.upper()
        if direction not in (Direction.LONG.value, Direction.SHORT.value):
            raise RejectedOrder("direction must be 'long' or 'short'")
        if not reasoning or not reasoning.strip():
            raise RejectedOrder("reasoning is required for every trade — explain WHY")
        if symbol not in self.settings.symbol_whitelist:
            raise RejectedOrder(
                f"symbol {symbol} is not on the whitelist {self.settings.symbol_whitelist}"
            )
        if self.position is not None:
            raise RejectedOrder(
                f"one position at a time: {self.position.symbol} position {self.position.id} is open"
            )
        if size < 1 or size > self.settings.max_position_size:
            raise RejectedOrder(
                f"size must be between 1 and {self.settings.max_position_size} contracts"
            )
        price = self.last_price.get(symbol)
        if price is None:
            raise RejectedOrder(
                f"no market data for {symbol} yet — cannot fill until at least one price tick arrives"
            )
        if stop is None:
            raise RejectedOrder("every order MUST include a stop loss")
        if direction == Direction.LONG.value and stop >= price:
            raise RejectedOrder(f"long stop {stop} must be below entry price {price}")
        if direction == Direction.SHORT.value and stop <= price:
            raise RejectedOrder(f"short stop {stop} must be above entry price {price}")
        if target is not None:
            if direction == Direction.LONG.value and target <= price:
                raise RejectedOrder(f"long target {target} must be above entry price {price}")
            if direction == Direction.SHORT.value and target >= price:
                raise RejectedOrder(f"short target {target} must be below entry price {price}")

        self.position = Position(
            id=uuid.uuid4().hex[:8],
            symbol=symbol,
            direction=Direction(direction),
            size=size,
            entry_price=price,
            stop=stop,
            initial_stop=stop,
            target=target,
            reasoning=reasoning.strip(),
        )
        self._save()
        return self.position

    def close(self, reasoning: str, price: Optional[float] = None) -> ClosedTrade:
        if self.position is None:
            raise RejectedOrder("no open position to close")
        if not reasoning or not reasoning.strip():
            raise RejectedOrder("reasoning is required to close a trade — explain WHY")
        exit_price = price if price is not None else self.last_price.get(self.position.symbol)
        if exit_price is None:
            raise RejectedOrder("no market data to price the exit")
        trade = self._close_at(exit_price, reasoning.strip())
        self._save()
        return trade

    def modify_stop(self, new_stop: float, reasoning: str) -> Position:
        pos = self._require_position(reasoning, "modify the stop")
        price = self.last_price.get(pos.symbol, pos.entry_price)
        if pos.direction == Direction.LONG and new_stop >= price:
            raise RejectedOrder(f"long stop {new_stop} must stay below current price {price}")
        if pos.direction == Direction.SHORT and new_stop <= price:
            raise RejectedOrder(f"short stop {new_stop} must stay above current price {price}")
        pos.stop = new_stop
        self._save()
        return pos

    def modify_target(self, new_target: Optional[float], reasoning: str) -> Position:
        pos = self._require_position(reasoning, "modify the target")
        if new_target is not None:
            price = self.last_price.get(pos.symbol, pos.entry_price)
            if pos.direction == Direction.LONG and new_target <= price:
                raise RejectedOrder(f"long target {new_target} must be above current price {price}")
            if pos.direction == Direction.SHORT and new_target >= price:
                raise RejectedOrder(f"short target {new_target} must be below current price {price}")
        pos.target = new_target
        self._save()
        return pos

    def flatten(self, reasoning: str) -> Optional[ClosedTrade]:
        """Close any open position at the last known price (kill switch)."""
        if self.position is None:
            return None
        exit_price = self.last_price.get(self.position.symbol, self.position.entry_price)
        trade = self._close_at(exit_price, reasoning)
        self._save()
        return trade

    # ---------- helpers ----------

    def _require_position(self, reasoning: str, action: str) -> Position:
        if self.position is None:
            raise RejectedOrder(f"no open position to {action}")
        if not reasoning or not reasoning.strip():
            raise RejectedOrder(f"reasoning is required to {action} — explain WHY")
        return self.position

    def _close_at(self, exit_price: float, exit_reasoning: str) -> ClosedTrade:
        pos = self.position
        assert pos is not None
        sign = 1.0 if pos.direction == Direction.LONG else -1.0
        points = (exit_price - pos.entry_price) * sign
        pnl = round(points * self.settings.point_value(pos.symbol) * pos.size, 2)
        risk_points = abs(pos.entry_price - pos.initial_stop)
        r_multiple = round(points / risk_points, 2) if risk_points > 0 else None

        trade = ClosedTrade(
            id=pos.id,
            symbol=pos.symbol,
            direction=pos.direction,
            size=pos.size,
            entry_price=pos.entry_price,
            initial_stop=pos.initial_stop,
            stop=pos.stop,
            target=pos.target,
            opened_at=pos.opened_at,
            entry_reasoning=pos.reasoning,
            exit_price=exit_price,
            pnl=pnl,
            r_multiple=r_multiple,
            exit_reasoning=exit_reasoning,
        )
        self.balance = round(self.balance + pnl, 2)
        day = datetime.now(timezone.utc).date().isoformat()
        self.daily_pnl[day] = round(self.daily_pnl.get(day, 0.0) + pnl, 2)
        self.closed_trades.append(trade)
        self.position = None
        return trade

    def snapshot(self) -> dict:
        today = datetime.now(timezone.utc).date().isoformat()
        unrealized = None
        if self.position is not None:
            price = self.last_price.get(self.position.symbol)
            if price is not None:
                sign = 1.0 if self.position.direction == Direction.LONG else -1.0
                unrealized = round(
                    (price - self.position.entry_price)
                    * sign
                    * self.settings.point_value(self.position.symbol)
                    * self.position.size,
                    2,
                )
        return {
            "as_of": utcnow_iso(),
            "balance": self.balance,
            "open_position": self.position.model_dump() if self.position else None,
            "unrealized_pnl": unrealized,
            "daily_pnl_today": self.daily_pnl.get(today, 0.0),
            "trades_closed_total": len(self.closed_trades),
            "last_prices": self.last_price,
        }
