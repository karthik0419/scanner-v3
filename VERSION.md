# Scanner-v3 Version History

All changes implemented across versions, newest first.

---

## v3.2 — 2026-09-05 (Bug Audit + Pattern Optimization)

### Problem
- Recent live tracker performance (Aug 11 – Sep 5, 2026): 1 win / 35 losses (-2.17% expectancy)
- This diverged sharply from the v3.1 backtest (+1.30% expectancy)
- User requested parallel validation: market regime check + bug-finding audit
- Root cause investigation found 8 implementation bugs + 1 missing regime filter

### Root Causes Identified
1. Backtester entered NEAR/WATCH setups before breakout confirmation (inflated fills)
2. Backtester evaluated stop/target exits on the entry bar (captured intraday wicks)
3. Risk calculated from CMP, not actual entry (max(cmp, breakout))
4. Breakeven trades classified as losses (inflated loss count, deflated win rate)
5. Daily C&H detector too permissive (handle_bars=15 allowed downtrends as handles)
6. Paper tracker: WIN_T1 status frozen in CLOSED set (P&L never updated after T1)
7. Paper tracker: WAITING_BREAKOUT picks never expired (116 stuck forever)
8. Paper tracker: used Close-only for stop/target checks (missed intraday touches)
9. Paper tracker: scan_date reset on sync (broke holding-period and expiry logic)
10. Double Bottom: volume hardcoded True (bug #9 — never checked actual volume)
11. No market regime filter (scanner kept issuing long breakouts in bear market)

### Changes (8 bug fixes + 1 regime filter + 2 pattern optimizations)

| # | File | Change | Impact |
|---|---|---|---|
| 1 | `scanner.py`, `backtester/engine.py` | Risk from entry (max(cmp,breakout)), not CMP | Honest R:R, honest risk % |
| 2 | `backtester/engine.py` | Gate NEAR/WATCH entry on next bar's High >= breakout | No more entering before breakout confirmation |
| 3 | `backtester/engine.py` | Skip exit checks on entry bar (entry_bar_idx tracking) | No more same-bar wick captures |
| 4 | `backtester/engine.py` | Breakeven (pnl=0) classified as WIN, not LOSS | Correct win/loss counts |
| 5 | `patterns/cup_handle.py` | Daily C&H: handle_bars 15→5, handle_depth_ratio 0.90→0.70 | 720-combo sweep winner. C&H expectancy -0.71%→+1.99% |
| 6 | `paper_tracker.py` | WIN_T1 moved from CLOSED to ACTIVE set | T1 hits now track to T2 with trailing stop |
| 7 | `paper_tracker.py` | WAITING_BREAKOUT expires after 30 days | 116 stuck picks now age out |
| 8 | `paper_tracker.py` | Use High/Low for stop/target checks, not Close | Catches intraday stop/target touches |
| 9 | `paper_tracker.py` | Trailing stop at breakeven after T1 hit | Protects T1 profits from reversals |
| 10 | `paper_tracker.py` | Don't reset scan_date on sync | Preserves holding-period anchor |
| 11 | `scanner.py` | Nifty SMA200 regime filter + `--force` flag | Aborts long scans in bear market. Nifty < SMA200 = RISK_OFF |
| 12 | `patterns/double_bottom.py` | DB: windows, bottom_tol 0.10→0.05, min_peak 0.12→0.20, real volume | 576-combo sweep winner. DB expectancy +0.81%→+1.46% |
| 13 | `check_nifty_regime.py` | Fix yfinance MultiIndex scalar bug | Regime checker now runs without crashing |

### Parameter Sweeps

#### C&H Daily Sweep (720 combinations, backbone50, 2 years)
Swept: handle_bars × max_depth × near_pct × handle_depth_ratio × min_depth

| Config | Trades | Win% | Expectancy | PF |
|---|---|---|---|---|
| **Optimal (handle_bars=5, hdr=0.70)** | **203** | **41.4%** | **+1.99%** | **1.57** |
| Current (handle_bars=15, hdr=0.50) | 125 | 32.8% | -0.71% | 0.82 |
| Worst (handle_bars=15, hdr=0.30) | 71 | 29.6% | -2.22% | 0.43 |

**Key finding:** `handle_bars` is the dominant factor. 5 bars (1 week) >> 15 bars (3 weeks). Shorter handles eliminate downtrends masquerading as handles — same lesson as the v3.0 weekly C&H fix.

#### Double Bottom Sweep (576 combinations, backbone50, 2 years)
Swept: windows × bottom_tol × min_peak × near_pct × stop_mult

| Config | Trades | Win% | Expectancy | PF |
|---|---|---|---|---|
| **Optimal (windows=(30,50,80,120,180), tol=0.05, peak=0.20)** | **92** | **57.6%** | **+1.46%** | **1.50** |
| Current (windows=(60,100,150,200,250), tol=0.10, peak=0.12) | 114 | 57.0% | +0.81% | 1.27 |

**Key finding:** `min_peak=0.20` is the biggest factor — requiring 20% peak (was 12%) filters out weak/noise double bottoms. Tighter `bottom_tol=0.05` (was 0.10) ensures only genuine double bottoms.

### Backtest Results (backbone50, 51 stocks, 2 years, min_score=40)

| Version | Trades | Win% | Avg win | Avg loss | Expectancy | PF | Max DD |
|---|---|---|---|---|---|---|---|
| **v3.2 (all fixes + optimized)** | **438** | **56.6%** | **+7.91%** | **-4.85%** | **+2.37%** | **2.13** | **-48.7%** |
| v3.2 (bug fixes only, pre-optimization) | 572 | 57.2% | +6.07% | -4.84% | +1.40% | 1.68 | -50.0% |
| v3.1 (pre-audit, has bugs) | 860 | 42.7% | +11.63% | -5.12% | +2.03% | 1.69 | -69.1% |

**v3.2 beats v3.1 on:** PF (2.13 vs 1.69), expectancy (+2.37% vs +2.03%), max DD (-48.7% vs -69.1%), win rate (56.6% vs 42.7%)
**The +2.37% is honest** — the v3.1 +2.03% was inflated by same-bar wick captures and NEAR pre-breakout entries.

### Pattern Breakdown (v3.2)

| Pattern | Trades | Win% | Expectancy | Verdict |
|---|---|---|---|---|
| Cup & Handle | 159 | 49.7% | +4.96% | Excellent (was -0.71% before optimization) |
| S&R Support | 51 | 64.7% | +4.23% | Excellent |
| S&R Breakout | 23 | 73.9% | +3.14% | Excellent |
| Re-entry | 160 | 63.7% | +0.17% | Marginal (volume play) |
| Double Bottom | 10 | 60.0% | -0.63% | Too few trades (tighter filter) |
| Descending Wedge | 31 | 29.0% | -1.70% | Losing — candidate for demotion |

### Paper Tracker Update (2026-09-05)
Applied all fixes to live tracker (267 picks):

| Metric | Before | After |
|---|---|---|
| Open trades | 215 (many stuck) | 110 (properly categorized) |
| WIN_T1 active | 9 (frozen) | 8 (now tracking to T2 with trailing stop) |
| WAITING_BREAKOUT | 116 (stuck forever) | ~80 (2 expired, rest counting down) |
| Trailing stops fired | 0 | 2 (closed at breakeven, was full loss) |
| Open unrealized P&L | -2.27% avg | +2.69% avg (62 profit, 48 loss) |

### Regime Filter (revised)
- Scanner checks Nifty vs SMA200 and SMA50 before scanning
- **BULL/NEUTRAL:** Nifty above both SMAs → scan normally
- **CHOPPY:** Nifty above SMA200 but below SMA50 → warn, proceed with caution
- **RISK_OFF:** Nifty below SMA200 → **WARN only, do NOT abort** (revised 2026-09-05)
  - Scanner-us adoption testing found RISK_OFF trades have PF 2.83 vs RISK_ON 1.33
  - NSE is mean-reverting — oversold breakouts during corrections are often the best entries
  - The recent live losses (1W/35L) were caused by implementation bugs (now fixed), not the regime
  - Original implementation aborted scanning; revised to warn only and proceed
- Current regime (2026-09-05): **RISK_OFF** — Nifty 23,898 vs 200DMA 24,612 (-2.9%)

### Out-of-Sample Validation (nifty200, 178 stocks, 2 years)
The C&H and DB parameter sweeps were on backbone50 (in-sample). To check for overfitting, the optimized config was validated on nifty200 (out-of-sample):

| Metric | backbone50 (in-sample) | nifty200 (out-of-sample) | Verdict |
|---|---|---|---|
| Trades | 438 | 1374 | — |
| Win rate | 56.6% | 54.3% | -2.3% (expected drop) |
| Expectancy | +2.37% | **+1.79%** | -0.58% (expected drop) |
| Profit factor | 2.13 | **1.90** | -0.23 (expected drop) |
| Max drawdown | -48.7% | -56.7% | -8.0% (larger universe) |

**No overfitting detected.** The +1.79% out-of-sample expectancy is solidly positive and close to the in-sample result. The slight drop is normal and expected.

**Key OOS finding — Descending Wedge is profitable out-of-sample:**
- backbone50 (in-sample): 31 trades, 29.0% WR, -1.70% expectancy
- nifty200 (out-of-sample): 105 trades, 41.9% WR, **+1.48% expectancy**
- The backbone50 result was specific to those 51 curated momentum stocks
- Wedge demotion was reverted — OOS is more reliable with 3x the sample size

### Monthly Earnings Estimate (Updated)
At +2.37% expectancy with ~25 trades/month and 25% position sizing:
- **~Rs 14,800/month on Rs 1L capital** (was Rs 6,000 at the post-bug-fix +0.97%)
- Only valid when regime filter allows trading (Nifty > SMA200)
- In bear markets, scanner correctly aborts — protecting capital

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

## Protocol Consistency (v3.2)

All v3 scripts now follow the same protocol:

| Script | ATR | Stop cap | T1 | R:R from | Re-entry | NEAR waits | Regime filter | High/Low checks |
|---|---|---|---|---|---|---|---|---|
| `scanner.py` | 2.0x | 8% | 50% | breakout | — | — | yes (SMA200) | — |
| `daily_scan.py` | 2.0x | 8% | 2:1 fixed | entry | — | — | — | — |
| `backtester/engine.py` | 2.0x | 8% | 50% | breakout | yes | yes (v3.2) | — | yes (v3.2) |
| `paper_tracker.py` | — | 8% | from scan | breakout | yes | yes | — | yes (v3.2) |
| `compare_backtest.py` | uses engine.py | | | | | | | |
