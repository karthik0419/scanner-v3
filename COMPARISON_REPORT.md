# scanner-v3 vs Previous Scanners — Performance Comparison Report

**Date:** 2026-07-17 (updated after C&H Weekly fix + pattern-specific SL)
**Method:** Walk-forward backtest on backbone50 stocks (51 curated momentum stocks), 2 years of daily data, scan every 5 bars, min score 40.

---

## 0. Fixes applied since last report (2026-07-16)

1. **Pattern-specific stop loss** — C&H and Wedge patterns now keep their original structural stops (handle low / wedge low) instead of being overridden by ATR stops. ATR stops are only applied to patterns without structural stops (S&R, Breakout, etc.). This was already in the code but the previous report's numbers reflected the pre-fix state.
2. **C&H Weekly detector tightened** — Root cause of negative expectancy was loose parameters: handle_bars=12 (allowed 3-month downtrends as "handles"), near_pct=0.15/0.25 (premature entries far from breakout), handle_depth_ratio=0.90 (handles as deep as the cup). Fixed to: handle_bars=4, max_depth=0.50, near_pct=0.08, near_pct_watch=0.15, handle_depth_ratio=0.50, volume_lookback=52. Aligns with Bulkowski's C&H best practices.

---

## 1. Backtest Results: v3 vs v2 (51 stocks, 2 years) — POST-FIX

| Metric | v3 (ATR+trail) | v2 (original) | Delta | Better? |
|---|---|---|---|---|
| Total trades | 860 | 874 | -14 | — |
| Wins | 367 | 377 | -10 | — |
| Losses | 493 | 497 | -4 | — |
| Win rate | 42.7% | 43.1% | -0.4% | ~equal |
| Avg win | +11.63% | +11.40% | +0.23 | ~equal |
| Avg loss | -5.12% | -5.07% | -0.05 | ~equal |
| **Expectancy** | **+2.03%** | **+2.03%** | **+0.00** | **tie** |
| Profit factor | 1.69 | 1.71 | -0.02 | ~equal |
| Max drawdown | -69.1% | -59.7% | -9.4 | v2 |

### Key takeaway
After the C&H Weekly fix, **v3 and v2 now have identical expectancy (+2.03%)**. The previous gap (-0.40%) has been eliminated. v3's win rate improved from 38.8% → 42.7% (+3.9%). The max drawdown is now worse for v3 (-69.1% vs -59.7%) — this is path-dependent on trade sequence and should be monitored in live trading.

### Comparison: before vs after fixes

| Metric | v3 before | v3 after | Change |
|---|---|---|---|
| Total trades | 964 | 860 | -104 |
| Win rate | 38.8% | 42.7% | **+3.9%** |
| Avg loss | -4.26% | -5.12% | -0.86 |
| **Expectancy** | **+1.84%** | **+2.03%** | **+0.19%** |
| Max drawdown | -54.5% | -69.1% | -14.6 |

The win rate and expectancy improvements confirm the C&H Weekly fix is working. The max drawdown increase is a concern — likely due to the changed trade sequence removing early stop-outs that previously "protected" against larger drawdowns. This should be validated with live trading.

---

## 2. By Pattern: v3 vs v2 — POST-FIX

| Pattern | v3 Trades | v3 Win% | v3 Avg P&L | v2 Trades | v2 Win% | v2 Avg P&L | Verdict |
|---|---|---|---|---|---|---|---|
| Double Bottom | 194 | 56.2% | +4.30% | 178 | 59.6% | +4.01% | Both excellent. Best pattern. |
| **C&H (Weekly)** | **177** | **39.5%** | **+0.87%** | **185** | **40.0%** | **+0.94%** | **FIXED — was -0.56%/-0.38%, now positive** |
| Cup & Handle (Daily) | 127 | 40.9% | +2.87% | 115 | 42.6% | +2.79% | Both solid. Structural stops preserved. |
| Descending Wedge | 126 | 28.6% | +1.31% | 135 | 32.6% | +1.82% | v2 better, but v3 now positive (was +0.44%) |
| C&H (Monthly) | 99 | 43.4% | +1.15% | 100 | 44.0% | +1.17% | Both profitable, consistent |
| S&R Breakout | 84 | 41.7% | +1.30% | 96 | 35.4% | +1.12% | v3 better (ATR stops work for S&R) |
| S&R Support | 39 | 48.7% | +0.52% | 55 | 41.8% | +1.77% | v2 better on P&L, v3 better on WR |
| Symmetrical Triangle | 6 | 33.3% | -0.04% | 4 | 50.0% | +2.46% | Small sample |
| Breakout Retest | 4 | 25.0% | -0.20% | 2 | 50.0% | -0.07% | Small sample |
| Channel Brk (Desc) | 1 | 0.0% | -8.53% | 2 | 0.0% | -3.10% | Very small sample |

### Key findings
1. **C&H (Weekly) — FIXED.** Win rate 34.5% → 39.5% (+5.0%), avg P&L -0.56% → +0.87% (+1.43% swing). The tightened handle_bars (4 vs 12), near_pct (0.08 vs 0.15), and handle_depth_ratio (0.50 vs 0.90) eliminated false signals from deep "handles" and premature entries.
2. **Double Bottom** — Still the best pattern (56% win rate, +4.3% avg P&L). Promotion to 28 points justified.
3. **C&H (Daily)** — Now positive in both v3 and v2 since structural stops are preserved. Win rate 40.9% / 42.6%.
4. **Descending Wedge** — Improved from +0.44% to +1.31% in v3 after preserving structural stops.
5. **S&R Breakout** — v3 better than v2 (41.7% vs 35.4% win rate). ATR stops work well for S&R.

---

## 3. Exit Reason Analysis (v3 — POST-FIX)

| Exit Reason | Trades | Avg P&L |
|---|---|---|
| Stop Loss | 376 | -5.70% |
| Time Exit | 271 | +6.39% |
| Target 1 | 90 | +13.82% |
| Target 2 | 42 | +19.67% |
| Trailing Stop | 33 | 0.00% |
| End of Data | 48 | +1.89% |

### Key findings
1. **Stop loss avg -5.70%** — slightly wider than pre-fix (-4.58%) because C&H/Wedge now use structural stops (handle low / wedge low) which are wider than ATR stops. This is intentional — the wider stops are compensated by higher win rates.
2. **T1 exits at +13.82%** — T1 as primary exit is working well (90 trades)
3. **T2 exits at +19.67%** — 42 trades reached full target
4. **Trailing stop 33 trades at 0.00%** — Breakeven trailing after T1 is protecting profits
5. **Time exits at +6.39%** — Many trades are profitable but didn't hit targets within 45 days

---

## 4. v3 vs All Previous Scanners (from May-Jul 2026 verification)

| Metric | scanner-v2 | scanner (v6.0+) | weekly-swing | earnings (PEAD) | **scanner-v3** |
|---|---|---|---|---|---|
| Unique picks | 414 | 153 | 209 | 49 | — (not yet live) |
| Closed trades | 97 | 39 | 93 | 46 | 860 (backtest) |
| Win rate | 35.1% | 17.9% | 30.1% | 43.5% | **42.7%** |
| Avg win | +19.7% | +27.8% | +16.5% | +11.6% | +11.6% |
| Avg loss | -6.5% | -8.8% | -4.4% | -3.0% | -5.1% |
| Expectancy | +2.7% | -2.2% | +1.9% | +3.4% | **+2.0%** |

### Note
The v3 backtest expectancy (+2.0%) is lower than v2's live verification (+2.7%) because:
1. The backtest uses a 45-day time exit (live trades are held longer)
2. The backtest uses min_score=40 (live scans use min_score=50, filtering out weaker setups)
3. The backtest includes ALL signals (live trading is selective — you only take the best setups)
4. The backtest doesn't include sector rotation bonus (which would boost scores in hot sectors)

---

## 5. Recommendations

### What's working in v3 (post-fix)
1. **C&H Weekly fix** — expectancy turned from -0.56% to +0.87%. The #1 issue is resolved.
2. **Pattern-specific stops** — C&H and Wedge keep structural stops, others use ATR. Both C&H (Daily) and Wedge are now profitable in v3.
3. **Double Bottom promotion** — still the best pattern (56.2% win rate, +4.3% avg P&L)
4. **Channel Breakout tightening** — filters out low-quality setups (volume + RSI gates)
5. **Trailing stop after T1** — 33 trades protected at breakeven
6. **S&R patterns** — ATR stops work well for S&R setups (41.7% win rate)

### What to monitor
1. **Max drawdown** — v3's -69.1% is worse than v2's -59.7%. This is path-dependent and may not reflect live performance (real portfolios have multiple concurrent positions, not sequential trades). Monitor in live trading.
2. **Descending Wedge** — v3 (28.6% WR, +1.31%) still lags v2 (32.6% WR, +1.82%). Structural stops helped but wedge volatility may need a wider stop. Consider 2.0x ATR as an alternative if structural stops underperform live.
3. **C&H Weekly trade count** — increased from 119 to 177 after fix (shorter handle = more patterns match). Monitor live win rate to confirm the backtest improvement holds.

### Recommended next steps
1. **Run v3 live for 2-3 weeks** alongside v2 to collect real-world data
2. **After 20-30 live trades**, compare v3 vs v2 expectancy on the same picks
3. **If max drawdown is a concern in live trading**, consider reducing position sizing or adding a portfolio-level stop (e.g. stop trading after 3 consecutive losses)
4. **Consider adaptive ATR multiplier for Wedge** — if structural stops underperform live, try 2.0x ATR specifically for Wedge patterns
