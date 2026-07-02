# Trading Rules — NQ/MNQ Sweep Reversal (v0.1 DRAFT)

The rulebook Claude follows. Every trade action must cite the rule number that
justifies it. Rules marked **[CODE]** are (or will be) enforced server-side in
the risk module; **[CLAUDE]** are judgment rules Claude applies; **[ISAAC]**
are human pre-market duties. Items marked **TBD** are awaiting Isaac's answer.

## R0 — Scope

- **R0.1** Instrument: MNQ only (NQ later, only after sizing up is earned).
  [CODE: symbol whitelist]
- **R0.2** Trade window: 8:30–10:00 AM CT (9:30–11:00 AM ET). No entries
  outside the window. [CODE]
- **R0.3** Flat by 10:00 AM CT no matter what. [CODE: auto-flatten]
- **R0.4** No trading on CPI or FOMC days. Bot stays PAUSED; Isaac simply does
  not activate it. [ISAAC — part of the daily checklist]

## R1 — Pre-market preparation (8:00–8:25 CT)

- **R1.1** Isaac reads 4H/1H and decides where price is drawing to. [ISAAC]
- **R1.2** Isaac marks the levels that matter today: overnight high/low,
  previous day high/low, equal highs/lows. [ISAAC → communicated to the bot;
  mechanism: TBD (morning briefing in chat vs. levels endpoint)]
- **R1.3** Isaac sets today's allowed direction:
  - HTF drawing up → longs only (sweeps of lows)
  - HTF drawing down → shorts only (sweeps of highs)
  - Chop/unclear → both allowed at half size, or skip the day entirely
  [ISAAC sets bias; CODE rejects trades against it]

## R2 — The setup (all three, in order)

- **R2.1 Sweep**: a wick trades through a marked R1.2 level and rejects
  (closes back on the correct side). [CLAUDE, from SWEEP_* signals]
  - Rejection definition: TBD (same candle close-back vs. within N candles)
- **R2.2 Displacement**: immediately after the sweep, a violent candle in the
  opposite direction that breaks a 1–5m swing and leaves an FVG.
  [CLAUDE, from DISPLACEMENT / FVG_CREATED signals]
  - "Violent" quantified: TBD (proposed: candle body ≥ 1.5× the average body
    of the prior 10 candles AND closes beyond the swing)
- **R2.3 Entry**: at the FVG midpoint on the retrace. [CLAUDE]
  - v1 execution: enter when price trades back into the gap (FVG_ENTERED),
    as close to midpoint as the feed allows. True resting limit orders: TBD
    (Phase 3 enhancement).
- **R2.4** Sweep with NO displacement = breakout day = no trades at all,
  in either direction, for the rest of the session. [CLAUDE]
- **R2.5** Direction must match the R1.3 bias. [CODE]

## R3 — Risk per trade

- **R3.1** Stop: beyond the sweep wick. NEVER widened — stops may only move
  toward price (tighten), never away. [CODE: reject widening modifications]
- **R3.2** Size: 1% of account per trade; contracts = dollar risk ÷ (stop
  distance × point value), rounded DOWN. [CODE computes/validates]
- **R3.3** Target: the opposite liquidity pool (from R1.2 marks). [CLAUDE]
- **R3.4** Optional partial at 2R, runner to the pool. v1: TBD — proposed to
  skip partials until the account supports split exits; all-out at target.
- **R3.5** Early kill: if price CLOSES through the FVG without reacting
  (= FVG_INVERTED against the position), exit immediately. [CLAUDE]

## R4 — Daily governors

- **R4.1** Max 2 trades per day. [CODE]
- **R4.2** 2 losses = done for the day; bot auto-PAUSES. [CODE]
- **R4.3** No setup = no trade. Sitting out is a correct outcome and gets
  logged as such (log_skipped_setup). [CLAUDE]

## Signal vocabulary this playbook requires

| Signal | Source | Status |
|---|---|---|
| TICK (1m) | FVG Narrator on MNQ 1m | needs MNQ chart alert |
| FVG_CREATED / ENTERED / MITIGATED / INVERTED | FVG Narrator | live (MES 5m); needs MNQ 1m |
| NEW_SWING_HIGH / LOW, BULLISH/BEARISH_BREAK | SMC Structure | live (MES 5m); needs MNQ |
| SWEEP_HIGH / SWEEP_LOW (of ONH/ONL/PDH/PDL/EQH/EQL) | Narrator v2 | **to build** |
| DISPLACEMENT | Narrator v2 | **to build** |

## Open questions (blocking full activation)

1. R2.1 rejection: same-candle close-back, or allow rejection within 2–3 candles?
2. R2.2 displacement: accept proposed 1.5× body definition, or your own number?
3. Equal highs/lows: how close is "equal"? (proposed: within 2 ticks / 0.50 NQ pts)
4. R1.2/R1.3 delivery: morning chat briefing to Claude, or a `botctl bias/levels`
   command? (proposed: chat briefing v1 — it's also a natural kill-switch moment)
5. R3.4 partials: confirm skip for v1?
6. Which chart drives the narrator: 1m (proposed) with 5m for context?
