# MCP Trading Bot — Phase 1

An MCP (Model Context Protocol) server that connects Claude to TradingView paper
trading. TradingView alerts fire webhooks into a small FastAPI server; Claude
connects over MCP to read signals, manage a **simulated** paper account, and log
every decision with written reasoning.

**Paper trading ONLY.** There is no connection to any live or prop-firm account,
by design.

## Architecture

```
TradingView alert ──webhook──▶ Bot server (FastAPI, port 8000)
                                 ├── signal store   (data/signals.jsonl)
                                 ├── paper account  (data/account.json)
                                 ├── trade log      (data/trade_log.jsonl)
                                 └── control state  (data/control.json)
                                        ▲                    ▲
Claude ◀──MCP (stdio)── mcp_server.py ──┘      botctl.py ────┘  (Isaac's kill switch)
```

Two processes:

1. **Bot server** (`run_server.py`) — receives TradingView webhooks, simulates
   fills, enforces guardrails, owns all state. Runs 24/7 on the EC2 box.
2. **MCP server** (`mcp_server.py`) — thin stdio bridge that Claude Desktop /
   Claude Code launches; it talks to the bot server's HTTP API.

## Safety model (Phase 1 guardrails, enforced in code)

- Bot starts **PAUSED**. Trading requires Isaac to run `botctl.py active`.
- Claude can pause or stop the bot, but **cannot** set it to ACTIVE.
- `STOPPED` = kill switch: flattens any open position instantly.
- Every order **must** include a stop loss on the correct side, or it's rejected.
- One position at a time; symbol whitelist; per-order size cap.
- `reasoning` is a required parameter on every trade action; every action is
  journaled to `data/trade_log.jsonl` the moment it happens.
- Signals not listed in `data/signal_definitions.json` are flagged
  **observe/log only** — Claude must not trade on them.

(Full risk profiles — Lucid-style trailing drawdown, daily loss limits, etc. —
are Phase 3.)

## Setup (Isaac: run these on the EC2 box)

```bash
cd mcp-trading-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# Edit .env: set WEBHOOK_SECRET to the output of:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

set -a; source .env; set +a
.venv/bin/python run_server.py
```

Run the test suite any time with `.venv/bin/python -m pytest tests/ -q`.

### Exposing the webhook to TradingView

TradingView only delivers webhooks to ports **80 and 443**. Easiest path on EC2:
put [Caddy](https://caddyserver.com) in front for automatic HTTPS
(`caddy reverse-proxy --from your-domain.com --to 127.0.0.1:8000`), or forward
port 80 → 8000 with nginx. Open only that port in the EC2 security group.

### Creating the TradingView alert

1. On your chart, open the indicator's **Add alert** dialog.
2. Check **Webhook URL** and paste: `https://<your-host>/webhook/<WEBHOOK_SECRET>`
3. Paste this as the **Message** (adjust `indicator`/`signal`/`direction` per alert —
   one alert per signal type is simplest):

```json
{"timestamp": "{{timenow}}", "symbol": "{{ticker}}", "timeframe": "{{interval}}", "indicator": "SMC", "signal": "BOS", "direction": "long", "price": {{close}}, "extra": {}}
```

Any Pine indicator can feed this same schema — that's the indicator-agnostic
design from the outline. When you add a new indicator, no code changes are
needed; just define its signals in `data/signal_definitions.json` so Claude is
allowed to trade on them, e.g.:

```json
{
  "BOS": "Break of structure — trend continuation in the stated direction.",
  "CHoCH": "Change of character — potential reversal signal."
}
```

### Connecting Claude (MCP)

Add to your Claude Desktop / Claude Code MCP config:

```json
{
  "mcpServers": {
    "trading-bot": {
      "command": "/path/to/mcp-trading-bot/.venv/bin/python",
      "args": ["/path/to/mcp-trading-bot/mcp_server.py"],
      "env": { "BOT_SERVER_URL": "http://127.0.0.1:8000" }
    }
  }
}
```

If Claude runs on a different machine than the bot server, point
`BOT_SERVER_URL` at the server (and firewall that port to your IP only).

## Controls (Isaac's toggle / kill switch)

```bash
python3 botctl.py status                 # current state + open position
python3 botctl.py active -m "NY session" # allow Claude to trade
python3 botctl.py pause  -m "lunch"      # observe/log only
python3 botctl.py stop   -m "kill it"    # KILL SWITCH: flatten + halt
python3 botctl.py account                # balance, P&L, position
python3 botctl.py log -n 20              # live journal, newest first
```

## MCP tools exposed to Claude

| Tool | Purpose |
|---|---|
| `get_current_signals(limit)` | Latest indicator events (undefined signals flagged observe-only) |
| `get_price_data(symbol, timeframe_minutes, bars)` | OHLC candles aggregated from received ticks |
| `get_account_state()` | Balance, open position, unrealized/daily P&L |
| `get_bot_status()` | ACTIVE / PAUSED / STOPPED + defined signals |
| `place_trade(direction, symbol, size, stop, reasoning, target?)` | Enter a paper trade — reasoning & stop required |
| `close_trade(reasoning, position_id?)` | Close the open position — reasoning required |
| `modify_stop(new_stop, reasoning)` / `modify_target(new_target, reasoning)` | Adjust exits — reasoning required |
| `get_trade_log(limit)` | Full journal: entries, exits, modifications, skips, rejections |
| `log_skipped_setup(reasoning, symbol?, rule_reference?)` | Record deliberate no-trade decisions |
| `pause_bot(reasoning, kill?)` | Claude can pause/stop itself — never activate |

## Notes & current limitations (Phase 1)

- **Fills are simulated** at the last received price; stops/targets trigger on
  incoming ticks. Alert-driven ticks are sparse — for finer exits, add a
  TradingView alert that fires every bar close (signal name `tick`) or plug a
  real data feed into `SignalStore.candles()` later.
- Phase 2 (rules doc), Phase 3 (Lucid-style risk profiles), and Phase 4
  (session reviews) build on top of this without structural changes.
