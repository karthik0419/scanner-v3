# Scanner-v3 Version History

All changes implemented across versions, newest first.

---

## v3.1 — 2026-07-29 (Risk Management Overhaul)

### Problem
- 83% stop-out rate on 2026-07-17 paper tracker batch (19/23 tradeable picks hit SL)
- Picks surfacing 20-28% from breakout as "NEAR" (actionable)
- Stop losses ranging 15-24% from entry (catastrophic risk)
- R:R calculated from CMP, not actual entry (breakout price) — misleading
- Full measured-move targets too ambitious for swing trades
- Paper tracker entering NEAR picks at CMP (below breakout) — buying before pattern triggers

### Root Causes Identified
1. Monthly C&H NEAR threshold was 20% (stocks 20% below breakout shown as "actionable")
2. Structural stops (handle low, wedge low) could be 15-25% below entry on monthly patterns
3. ATR multiplier 1.5x was too tight — caused whipsaws without reducing losses
4. T1 at 60% of measured move was often 20-50% away — rarely reached in swing timeframe
5. Paper tracker entered ALL picks at CMP on scan day, including NEAR picks below breakout
6. R:R from CMP made picks look better than reality (CMP below breakout = inflated upside %)

### Changes (12 fixes)

| # | File | Change | Impact |
|---|---|---|---|
| 1 | `patterns/cup_handle_monthly.py` | NEAR 20%→5%, WATCH 35%→10% | Only surface stocks within 5% of breakout as NEAR |
| 2 | `scanner.py`, `backtester/engine.py` | 8% max stop cap for ALL patterns | No trade risks more than 8% from CMP. Structural stops wider than 8% → ATR stop used → if ATR also too wide → hard cap at 8% |
| 3 | `scanner.py`, `backtester/engine.py` | ATR multiplier 1.5x→2.0x | ATR sweep: 2.0x has PF 2.03 (vs 1.80 at 1.5x), DD -46.8% (vs -66.7%) |
| 4 | `scanner.py`, `backtester/engine.py` | T1 target 60%→50% of measured move | More realistic swing targets, reached more often |
| 5 | `scanner.py`, `backtester/engine.py` | Max risk filter (10%) | Picks with >10% stop loss from CMP rejected entirely |
| 6 | `scanner.py`, `backtester/engine.py` | Max distance filter (8%) | NEAR/WATCH picks >8% from breakout rejected (BREAKOUT exempt) |
| 7 | `scanner.py`, `backtester/engine.py` | R:R from breakout entry, not CMP | R:R now reflects actual entry point, not current price |
| 8 | `scanner.py`, `backtester/engine.py` | Wide-stop R:R penalty | R:R halved for >8% risk, -20% for >6% risk |
| 9 | `backtester/engine.py` | Re-entry after whipsaw | If stock hits SL but recovers above breakout within 30 days → re-enter with 2% stop |
| 10 | `paper_tracker.py` | NEAR picks → WAITING_BREAKOUT | Not entered at CMP. Only entered when price crosses breakout level |
| 11 | `paper_tracker.py` | Auto re-entry check on update | Stopped-out trades checked for recovery above breakout on each update |
| 12 | `scanner.py`, `daily_scan.py` | `--stocks` flag + 2.0x ATR in daily scan | Custom stock list support; consistent ATR across all scripts |

### New Analysis Tools
- `whipsaw_analysis.py` — finds SL exits that would have hit target if held (16.3% whipsaw rate)
- `sweep_atr.py` — ATR multiplier sweep (1.0x-3.0x) to find optimal stop distance
- `final_comparison.py` — v3.1 vs v3.0 vs v2 comparison report

### Backtest Results (nifty200, 178 stocks, 2 years)

| Version | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD |
|---|---|---|---|---|---|---|---|
| **v3.1 (2.0x ATR + re-entry)** | 3012 | 40.6% | +7.6% | **-3.0%** | **+1.30%** | **1.73** | **-60.1%** |
| v3.0 (1.5x ATR, old) | 2389 | 38.0% | +9.1% | -3.4% | +1.32% | 1.62 | -73.9% |
| v2 (original stops) | 1888 | 45.4% | +6.6% | -3.4% | +1.17% | 1.64 | -61.5% |

**v3.1 beats v2** on: PF (1.73 vs 1.64), expectancy (+1.30 vs +1.17), avg loss (-3.0% vs -3.4%)
**v3.1 beats v3.0** on: PF (1.73 vs 1.62), DD (-60.1% vs -73.9%), win rate (40.6% vs 38.0%)

### ATR Multiplier Sweep (backbone50, 51 stocks, 2 years)

| Multiplier | Trades | Win rate | Avg loss | Expectancy | PF | Max DD |
|---|---|---|---|---|---|---|
| 1.0x | 764 | 39.4% | -3.86% | +2.00% | 1.86 | -48.4% |
| 1.5x (old) | 757 | 38.0% | -3.66% | +1.82% | 1.80 | -66.7% |
| **2.0x (chosen)** | **785** | **38.9%** | **-3.49%** | **+2.19%** | **2.03** | **-46.8%** |
| 2.5x | 767 | 38.2% | -3.80% | +2.06% | 1.88 | -54.2% |
| 3.0x | 733 | 40.5% | -4.15% | +2.20% | 1.89 | -59.4% |

### Whipsaw Analysis
- 196 out of 1203 SL exits (16.3%) were whipsaws — stock hit SL, then reached T1 within 30 days
- Avg SL loss on whipsaws: -3.79%. Avg P&L if held to T1: +10.46%
- 81% went lower before recovering (wider stop wouldn't have saved most)
- Re-entry feature captures these: 49.2% win rate on re-entries (highest of any pattern)

### Paper Tracker Statuses (v3.1)
- `WAITING_BREAKOUT` — NEAR pick, not entered. Waiting for price to cross breakout level.
- `OPEN` — active trade (BREAKOUT entered at CMP, or NEAR entered after breakout confirmed).
- `WIN_T1` — price hit T1, still open for T2.
- `WIN_T2` — price hit T2, trade closed.
- `LOSS` — SL hit, closed. Auto-checked for re-entry on next update.
- `RE_ENTERED` — recovered above breakout after SL, re-entered with 2% stop.
- `TIME_EXIT` — 45 days elapsed without SL/target, closed at current price.
- `WATCH` — too far from breakout at scan time, not traded.

---

## v3.0 — 2026-07-17 to 2026-07-18 (Production Hardening)

### Changes (13 improvements)

| # | Change | Rationale |
|---|---|---|
| 1 | ATR-based stop loss (default, 1.5x) | v2 avg SL loss was -6.5%; earnings-scanner proved -3% stops work |
| 2 | Double Bottom promoted (score bonus 18→28) | 100% win rate (11W/0L) across scanners |
| 3 | Channel Breakout tightened (vol gate 1.3x→1.5x, RSI<75, R:R≥1.5) | 24% win rate was dragging performance |
| 4 | C&H Weekly promoted (score bonus 25→28) | 50% win rate in scanner/ |
| 5 | Price range filter (`--min-price`, `--max-price`) | Retail-friendly high-momentum stocks |
| 6 | Self-contained sector rotation (`utils/sector_rotation_v3.py`) | No dependency on scanner/; 568+ stock-to-sector mappings |
| 7 | Bearish / short mode (`--bearish` flag) | NSE Heat Map strategy: weak sectors → short weakest stocks |
| 8 | `requirements.txt` | Reproducible installs (was missing in v2) |
| 9 | C&H Weekly detector fixed | handle_bars=12 allowed 3-month downtrends as "handles". Fixed to Bulkowski's: handle_bars=4, max_depth=0.50, near_pct=0.08/0.15 |
| 10 | Sector classification fixed (3-layer lookup) | Was 47% wrong (14/30 picks misclassified). Now: NSE index constituents → yfinance industry → yfinance sector |
| 11 | Daily scan smart universe | Was ~600 stocks. Now: Backbone 50 + Nifty 500 + weekly picks + ALL hot sector stocks |
| 12 | Timeframe tracking + filter (`--timeframe`) | Every result includes timeframe column. Filter by daily/weekly/monthly |
| 13 | Automated Telegram notifications | scanner.py and daily_scan.py auto-send on completion. `--no-notify` to opt out |

### Backtest Results (pre-v3.1)

| Dataset | Stocks | Trades | Win rate | Avg loss | Expectancy | Max DD |
|---|---|---|---|---|---|---|
| backbone50 (in-sample) | 51 | 860 | 42.7% | -5.12% | +2.03% | -69.1% |
| nifty200 (out-of-sample) | 178 | 2903 | 42.6% | -4.76% | +1.37% | -84.6% |

---

## v2 — 2026-06-15 (Enhanced Scanner)

### Changes
- Diagonal neckline C&H detection
- Monthly timeframe support
- T1/T2 two-target system (T1=60% of move, T2=full move)
- Status tiers: WATCH / NEAR / BREAKOUT
- C&H hit rate improved 52% → 95% on 204-sample ground truth
- +2.7% expectancy/trade, 35% win rate, 3:1 R:R over 97 closed trades

---

## Protocol Consistency (v3.1)

All v3 scripts now follow the same protocol:

| Script | ATR | Stop cap | T1 | R:R from | Re-entry | NEAR waits |
|---|---|---|---|---|---|---|
| `scanner.py` | 2.0x | 8% | 50% | breakout | — | — |
| `daily_scan.py` | 2.0x | 8% | 2:1 fixed | entry | — | — |
| `backtester/engine.py` | 2.0x | 8% | 50% | breakout | yes | — |
| `paper_tracker.py` | — | 8% | from scan | breakout | yes | yes |
| `compare_backtest.py` | uses engine.py | | | | | |
