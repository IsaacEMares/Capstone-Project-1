from __future__ import annotations

import hmac
import threading
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .account import PaperAccount, RejectedOrder
from .config import Settings
from .control import Control
from .models import Alert, BotState
from .signals import SignalStore
from .tradelog import TradeLog


class TradeRequest(BaseModel):
    direction: str
    symbol: str
    size: int = 1
    stop: float
    target: Optional[float] = None
    reasoning: str


class CloseRequest(BaseModel):
    position_id: Optional[str] = None
    reasoning: str


class ModifyRequest(BaseModel):
    new_stop: Optional[float] = None
    new_target: Optional[float] = None
    clear_target: bool = False
    reasoning: str


class ControlRequest(BaseModel):
    state: BotState
    reason: str = ""


class DecisionRequest(BaseModel):
    reasoning: str
    symbol: str = ""
    rule_reference: str = ""


class WebhookPayload(BaseModel):
    timestamp: str = ""
    symbol: str
    timeframe: str = ""
    indicator: str = "unknown"
    signal: str = "unknown"
    direction: str = "neutral"
    price: Optional[float] = None
    extra: dict[str, Any] = Field(default_factory=dict)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="MCP Trading Bot Server", version="0.1.0")
    account = PaperAccount(settings)
    control = Control(settings.data_dir)
    signals = SignalStore(settings.data_dir)
    log = TradeLog(settings.data_dir)
    lock = threading.Lock()

    def reject(status: int, why: str) -> HTTPException:
        log.append("rejected", reason=why)
        return HTTPException(status_code=status, detail=why)

    # ---------- TradingView webhook (Phase 1.2) ----------

    @app.post("/webhook/{secret}")
    def webhook(secret: str, payload: WebhookPayload):
        if not settings.webhook_secret:
            raise HTTPException(503, "server has no WEBHOOK_SECRET configured")
        if not hmac.compare_digest(secret, settings.webhook_secret):
            raise HTTPException(403, "bad webhook secret")
        alert = Alert(
            timestamp=payload.timestamp or Alert.model_fields["timestamp"].default_factory(),
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe,
            indicator=payload.indicator,
            signal=payload.signal,
            direction=payload.direction,
            price=payload.price,
            extra=payload.extra,
        )
        with lock:
            record = signals.add(alert)
            closed = None
            if alert.price is not None:
                closed = account.on_price(alert.symbol, alert.price)
            if closed is not None:
                log.append("exit", trade=closed.model_dump(), triggered_by="price tick")
        return {"stored": True, "signal_defined": record["defined"]}

    # ---------- read endpoints ----------

    @app.get("/signals")
    def get_signals(limit: int = 20):
        return signals.recent(limit)

    @app.get("/price_data")
    def price_data(symbol: str, timeframe_minutes: int = 5, bars: int = 50):
        return signals.candles(symbol, timeframe_minutes, bars)

    @app.get("/account")
    def get_account():
        return account.snapshot()

    @app.get("/log")
    def get_log(limit: int = 50):
        return log.recent(limit)

    @app.get("/status")
    def get_status():
        record = control.get()
        record["open_position"] = (
            account.position.model_dump() if account.position else None
        )
        record["signal_definitions"] = signals.defined_signals()
        return record

    # ---------- control (Phase 1.5) ----------

    @app.post("/control")
    def set_control(req: ControlRequest):
        with lock:
            previous = control.state
            record = control.set(req.state, req.reason or "manual toggle")
            flattened = None
            if req.state == BotState.STOPPED:
                trade = account.flatten("Kill switch: STOPPED — flatten all positions.")
                flattened = trade.model_dump() if trade else None
                if flattened:
                    log.append("exit", trade=flattened, triggered_by="kill switch")
            log.append(
                "control",
                from_state=previous.value,
                to_state=req.state.value,
                reason=req.reason,
            )
        return {"control": record, "flattened": flattened}

    # ---------- trading (Phase 1.3 order functions, guarded) ----------

    @app.post("/trade")
    def place_trade(req: TradeRequest):
        with lock:
            state = control.state
            if state != BotState.ACTIVE:
                raise reject(409, f"bot is {state.value} — trading is only allowed when ACTIVE")
            try:
                pos = account.enter(
                    direction=req.direction,
                    symbol=req.symbol,
                    size=req.size,
                    stop=req.stop,
                    target=req.target,
                    reasoning=req.reasoning,
                )
            except RejectedOrder as e:
                raise reject(422, str(e))
            log.append("entry", position=pos.model_dump(), reasoning=req.reasoning)
        return pos.model_dump()

    @app.post("/close")
    def close_trade(req: CloseRequest):
        with lock:
            if (
                req.position_id
                and account.position
                and account.position.id != req.position_id
            ):
                raise reject(404, f"no open position with id {req.position_id}")
            try:
                trade = account.close(req.reasoning)
            except RejectedOrder as e:
                raise reject(422, str(e))
            log.append("exit", trade=trade.model_dump(), triggered_by="close_trade")
        return trade.model_dump()

    @app.post("/modify")
    def modify(req: ModifyRequest):
        with lock:
            state = control.state
            if state == BotState.STOPPED:
                raise reject(409, "bot is STOPPED — no modifications allowed")
            try:
                if req.new_stop is not None:
                    pos = account.modify_stop(req.new_stop, req.reasoning)
                    log.append("modify_stop", new_stop=req.new_stop, reasoning=req.reasoning)
                if req.new_target is not None or req.clear_target:
                    pos = account.modify_target(
                        None if req.clear_target else req.new_target, req.reasoning
                    )
                    log.append(
                        "modify_target",
                        new_target=None if req.clear_target else req.new_target,
                        reasoning=req.reasoning,
                    )
            except RejectedOrder as e:
                raise reject(422, str(e))
            if req.new_stop is None and req.new_target is None and not req.clear_target:
                raise reject(422, "nothing to modify — provide new_stop and/or new_target")
        return pos.model_dump()

    @app.post("/decision")
    def log_decision(req: DecisionRequest):
        """Log a deliberate no-trade decision (Phase 4.1: 'saw setup, skipped it')."""
        if not req.reasoning.strip():
            raise HTTPException(422, "reasoning is required")
        record = log.append(
            "skip", symbol=req.symbol, rule_reference=req.rule_reference, reasoning=req.reasoning
        )
        return record

    return app


app = create_app()
