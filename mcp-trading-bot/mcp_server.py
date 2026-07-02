"""MCP server exposing the trading bot tools to Claude (Phase 1.4).

Runs over stdio and talks to the bot server's HTTP API (BOT_SERVER_URL).
Claude can observe, trade (only while the bot is ACTIVE), and pause/stop the
bot — but can NEVER set the bot to ACTIVE. Only Isaac can, via botctl.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("BOT_SERVER_URL", "http://127.0.0.1:8000")

mcp = FastMCP("tradingview-paper-bot")


def _request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        resp = httpx.request(method, f"{BASE_URL}{path}", timeout=10, **kwargs)
    except httpx.HTTPError as e:
        return {"error": f"bot server unreachable at {BASE_URL}: {e}"}
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        return {"rejected": detail, "status_code": resp.status_code}
    return resp.json()


@mcp.tool()
def get_current_signals(limit: int = 20) -> Any:
    """Latest indicator events received from TradingView, newest first.

    Signals flagged defined=false are NOT in the rules doc yet: observe and
    log only, never trade on them.
    """
    return _request("GET", "/signals", params={"limit": limit})


@mcp.tool()
def get_price_data(symbol: str, timeframe_minutes: int = 5, bars: int = 50) -> Any:
    """Recent OHLC candles for a symbol, aggregated from received price ticks."""
    return _request(
        "GET",
        "/price_data",
        params={"symbol": symbol, "timeframe_minutes": timeframe_minutes, "bars": bars},
    )


@mcp.tool()
def get_account_state() -> Any:
    """Paper account snapshot: balance, open position, unrealized P&L, daily P&L."""
    return _request("GET", "/account")


@mcp.tool()
def get_bot_status() -> Any:
    """Control state (ACTIVE / PAUSED / STOPPED), open position, defined signals."""
    return _request("GET", "/status")


@mcp.tool()
def place_trade(
    direction: str,
    symbol: str,
    size: int,
    stop: float,
    reasoning: str,
    target: Optional[float] = None,
) -> Any:
    """Enter a simulated paper trade. REQUIRES detailed reasoning: cite the
    signals, timeframes, and the Phase 2 rule(s) that justify this entry.

    direction: 'long' or 'short'. stop is mandatory (orders without a stop are
    rejected). Fills at the last known price for the symbol. Rejected unless
    the bot is ACTIVE.
    """
    return _request(
        "POST",
        "/trade",
        json={
            "direction": direction,
            "symbol": symbol,
            "size": size,
            "stop": stop,
            "target": target,
            "reasoning": reasoning,
        },
    )


@mcp.tool()
def close_trade(reasoning: str, position_id: Optional[str] = None) -> Any:
    """Close the open position at the last known price. REQUIRES reasoning
    (e.g. 'Closed at target' or 'Exited early: opposing 1-min CHoCH formed')."""
    return _request("POST", "/close", json={"position_id": position_id, "reasoning": reasoning})


@mcp.tool()
def modify_stop(new_stop: float, reasoning: str) -> Any:
    """Move the stop loss on the open position. REQUIRES reasoning."""
    return _request("POST", "/modify", json={"new_stop": new_stop, "reasoning": reasoning})


@mcp.tool()
def modify_target(new_target: Optional[float], reasoning: str) -> Any:
    """Move (or clear, by passing null) the take-profit target. REQUIRES reasoning."""
    payload: dict[str, Any] = {"reasoning": reasoning}
    if new_target is None:
        payload["clear_target"] = True
    else:
        payload["new_target"] = new_target
    return _request("POST", "/modify", json=payload)


@mcp.tool()
def get_trade_log(limit: int = 50) -> Any:
    """Full action journal, newest first: entries, exits, modifications,
    control changes, rejections, and skipped setups — each with reasoning."""
    return _request("GET", "/log", params={"limit": limit})


@mcp.tool()
def log_skipped_setup(reasoning: str, symbol: str = "", rule_reference: str = "") -> Any:
    """Log a deliberate 'saw setup, skipped it' decision with the rule that
    justified sitting out. Correctly doing nothing counts and must be recorded."""
    return _request(
        "POST",
        "/decision",
        json={"reasoning": reasoning, "symbol": symbol, "rule_reference": rule_reference},
    )


@mcp.tool()
def pause_bot(reasoning: str, kill: bool = False) -> Any:
    """Move the bot to PAUSED, or STOPPED (kill=True flattens all positions).

    Use when conditions look wrong (stale data, conflicting signals, limits
    near breach). Claude cannot reactivate the bot — only Isaac can, via botctl.
    """
    state = "STOPPED" if kill else "PAUSED"
    return _request("POST", "/control", json={"state": state, "reason": reasoning})


if __name__ == "__main__":
    mcp.run()
