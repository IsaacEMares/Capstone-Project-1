# Trading Rules — NQ/MNQ Sweep Reversal (v1.0)

The rulebook Claude follows. Every trade action must cite the rule number that
justifies it. Enforcement tags: **[CODE]** = server-enforced, Claude physically
cannot violate it; **[CLAUDE]** = judgment rule Claude applies; **[ISAAC]** =
human pre-market duty.

## R0 — Scope & schedule

- **R0.1** Instrument: MNQ only (NQ later, only after sizing up is earned).
  [CODE: symbol whitelist]
- **R0.2** Trade window: 8:30–10:00 AM CT. [CODE]
- **R0.3** No NEW entries after 9:30 AM CT — a trade needs room to work.
  Management of an open position continues until flat. [CODE]
- **R0.4** Flat by 10:00 AM CT no matter what. [CODE: auto-flatten + pause]
- **R0.5** No trading on CPI or FOMC days. Bot is simply never activated.
  [ISAAC — daily checklist]
- **R0.6** Mid-window scheduled releases (e.g., 9:00 CT data): no new entries
  within 5 minutes before/after the release. [CODE, from briefing news times]
  If a release prints while IN a trade: the trade keeps its stop and its
  rules — no panic exits; the stop is the risk. [CLAUDE]

## R1 — Pre-market preparation (8:00–8:25 CT)

- **R1.1** Isaac reads 4H/1H and decides where price is drawing to. [ISAAC]
- **R1.2** Isaac marks today's levels: overnight high/low, previous day
  high/low, equal highs/lows. (Narrator v2 also announces these
  automatically; Isaac's briefing is the authority when they disagree.)
  [ISAAC]
- **R1.3** Isaac sets today's allowed direction:
  - HTF drawing up → longs only (sweeps of lows)
  - HTF drawing down → shorts only (sweeps of highs)
  - Chop/unclear → both allowed at HALF size, or stand down entirely
  [ISAAC sets bias; CODE rejects trades against it]
- **R1.4** **No morning briefing = bot does not trade.** The briefing (bias +
  levels + news times) must be submitted before any entry is accepted.
  [CODE]

## R2 — The setup (all three, in order)

- **R2.1 Sweep**: a wick trades through a marked R1.2 level and REJECTS —
  price closes back inside the level within 2 candles on the execution
  timeframe (the sweep candle itself, or the very next). Longer hovering
  beyond the level is acceptance forming, not rejection. [CLAUDE, from
  SWEEP_LOW / SWEEP_HIGH signals]
- **R2.2 Displacement**: immediately after the sweep, a violent candle back
  the other way. All three, AND-ed: [CLAUDE, from DISPLACEMENT signals]
  1. body ≥ 1.5× the average body of the prior 10 candles
  2. breaks a 1–5m swing point
  3. leaves an FVG
- **R2.3 Entry**: limit-style at the FVG midpoint on the retrace. v1
  execution: enter when price trades back into the gap (FVG_ENTERED), as
  close to the midpoint as the feed allows. [CLAUDE]
- **R2.4 Acceptance kills the fade-side**: if price closes 2+ consecutive
  candles beyond a level and holds there, that side is DEAD for the day —
  that's acceptance (a real breakout), no fades against it. But if price
  comes back inside the range, a LATER sweep with full displacement is a
  valid fresh setup. A first sweep without displacement does NOT kill the
  day. [CLAUDE, from LEVEL_ACCEPTED signals]
- **R2.5** Direction must match the R1.3 bias. [CODE]
- **R2.6 Missed entry = no trade.** If price never retraces to the entry
  zone, the market didn't offer the trade. Never chase. Log as skipped
  setup (the log later informs midpoint-vs-edge entry tuning). [CLAUDE]
- **R2.7 Re-entry**: a stop-out invalidates the story (price traded back
  through the sweep extreme). No re-entering the same FVG. Re-entry
  requires a FRESH, COMPLETE setup — new sweep (or deeper raid of the same
  pool) + new displacement + new FVG. Full checklist from zero. One
  re-entry max, and it counts toward the daily trade cap. [CLAUDE + CODE cap]

## R3 — Risk per trade

- **R3.1** Stop: beyond the sweep wick. NEVER widened — stops may only move
  toward price, never away. [CODE: widening rejected]
- **R3.2** Size: 1% of account per trade; contracts = dollar risk ÷ (stop
  distance × point value), rounded DOWN. Half size on both-allowed days.
  [CODE validates]
- **R3.3** Target: nearest un-swept opposite liquidity pool (from R1.2
  marks). Conservatism wins v1. [CLAUDE]
- **R3.4** All-out at target — no partials in v1. Split exits come when
  account size supports 2+ contracts cleanly. [CLAUDE]
- **R3.5** Early kill: if price CLOSES through the FVG without reacting
  (FVG_INVERTED against the position), exit immediately. [CLAUDE]
- **R3.6** Breakeven: stop may move to BE only after the trade has reached
  +1R, never earlier (early BE donates winners to noise). Tighten-only per
  R3.1. [CODE: BE-before-1R rejected]

## R4 — Daily governors

- **R4.1** Max 2 trades per day. [CODE]
- **R4.2** 2 losses = flat, done for the day; bot auto-PAUSES. [CODE]
- **R4.3** No setup = no trade. Sitting out is a correct outcome and gets
  logged as such (log_skipped_setup). [CLAUDE]
- **R4.4** Sweep with no displacement = hands off THAT setup (see R2.4 for
  when the day reopens vs. dies). [CLAUDE]

## Signal vocabulary (all on MNQ1!, 1-minute execution chart)

| Signal | Source | Meaning |
|---|---|---|
| TICK | FVG Narrator | 1m bar close price feed |
| FVG_CREATED / ENTERED / MITIGATED / INVERTED | FVG Narrator | gap lifecycle |
| NEW_SWING_HIGH / NEW_SWING_LOW | SMC Structure | structure mapping |
| BULLISH_BREAK / BEARISH_BREAK | SMC Structure | BOS/CHoCH (context decides which) |
| SWEEP_HIGH / SWEEP_LOW | Sweep Narrator v2 | wick through PDH/PDL/ONH/ONL/EQH/EQL + rejection ≤2 candles |
| LEVEL_ACCEPTED | Sweep Narrator v2 | 2+ closes beyond a level — fade-side dead (R2.4) |
| DISPLACEMENT | Sweep Narrator v2 | R2.2 candle (body×1.5 + swing break + FVG), with gap bounds |

## Change log

- v1.0 — Isaac's rulings incorporated: acceptance-based day-kill (R2.4),
  re-entry tightening (R2.7), BE after 1R (R3.6), 9:30 entry cutoff (R0.3),
  news buffer + no-panic-exit (R0.6), nearest-pool target (R3.3), 2-candle
  sweep rejection (R2.1), 3-part AND displacement (R2.2), no partials v1
  (R3.4), briefing-required moved to [CODE] (R1.4).
- v0.1 — initial draft from Isaac's playbook.
