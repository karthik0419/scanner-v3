As an AI assistant (Inkling), please review this codebase for bugs and what it brings.

Project: scanner-v3 (restaurant POS SaaS + stock trading scanner hybrid — but focus on scanner)
Repo: https://github.com/karthik0419/scanner-v3
Branch: master (latest commit 31758e2)

Key files to review:
- scanner.py (main scanner engine)
- backtester/engine.py (backtest with re-entry)
- daily_scan.py (daily morning scanner)
- paper_tracker.py (live trade tracking with sync/re-entry)
- patterns/double_bottom.py (pattern detector)
- patterns/cup_handle_monthly.py (monthly C&H detector)
- VERSION.md (version history)
- AGENTS.md (workspace documentation)

What v3.1 changed:
1. ATR multiplier 1.5x → 2.0x (after sweep test)
2. 8% max stop cap for ALL patterns (was structural only for C&H)
3. Monthly C&H NEAR threshold 20% → 5%, WATCH 35% → 10%
4. T1 target 60% → 50% of measured move
5. Max risk filter: reject picks >10% risk
6. Max distance filter: reject NEAR/WATCH >8% from breakout
7. R:R calculated from breakout entry (not CMP)
8. R:R penalty: halved for >8% risk, -20% for >6% risk
9. Re-entry feature: after SL, if stock recovers above breakout within 30 days → re-enter with 2% stop
10. Smart universe: Backbone50 + Nifty500 + hot sector stocks (adapts daily)
11. `--stocks` flag for custom lists
12. Paper tracker: NEAR picks start as WAITING_BREAKOUT (not entered at CMP), BREAKOUT = OPEN
13. Paper tracker sync: merges new scan picks without losing ongoing trades
14. Post-scan interactive prompt for breakout/re-entry check

Backtest results (nifty200, 178 stocks, 2 years):
- v3.1 (2.0x ATR + re-entry): 3012 trades, 40.6% WR, +1.30% exp, PF 1.73, DD -60.1%, avg loss -3.0%
- v3.0 (1.5x ATR): 2389 trades, 38.0% WR, +1.32% exp, PF 1.62, DD -73.9%, avg loss -3.4%
- v2 (original): 1888 trades, 45.4% WR, +1.17% exp, PF 1.64, DD -61.5%, avg loss -3.4%
- Re-entry trades: 691, 49.2% WR, +0.58% avg (highest of any pattern)
- Whipsaw rate: 16.3% of SL exits recover to T1 (81% went lower before recovering)

Issues I see:
- v3.1 win rate (40.6%) is lower than v2 (45.4%) — tighter stops = more frequent stops
- v3.1 trades more (3012 vs 1888) — more signals = more chances to lose
- Expectancy is similar (+1.30 vs +1.17) — improvement is in smaller losses, not bigger wins
- Re-entry trades have positive expectancy but dilute per-trade profit (+0.58% avg vs +2.19% overall)
- Max drawdown is still -60% — not great for live trading
- The 2-week ranking uses backtest stats (which include re-entry) — may overestimate short-term probability
- Daily scan (`daily_scan.py`) uses a different stop logic (2.0x ATR, structural + ATR hybrid) — needs verification it matches scanner.py exactly
- Paper tracker `update` uses `_fetch_nse` which sometimes fails (delisted symbols, rate limits) — may miss breakout detection
- Whipsaw analysis uses `backtest_v3.csv` which includes re-entry trades — the analysis compares SL exits to T1 hits, but some of those T1 hits may be from re-entry trades, not the original trade

What does v3.1 bring? What's missing? Any bugs?
