# Swing Scanner v3 — Production

NSE swing trading setup scanner. Built on scanner-v2 (proven +2.7% expectancy per trade, 35% win rate, 3:1 R:R over 97 closed trades).

## What's new in v3.2 (2026-09-05)

### Bug audit + pattern optimization (2026-09-05)

After live tracker showed 1 win / 35 losses (-2.17% expectancy) vs +1.30% backtest promise, a full audit found 8 implementation bugs + 1 missing regime filter. After fixing, two parameter sweeps (720 C&H combos + 576 DB combos) optimized the two most important patterns.

| # | Change | Evidence | Impact |
|---|---|---|---|
| 31 | **8 implementation bugs fixed** | Backtester entered NEAR before breakout, captured same-bar wicks, risk from CMP not entry, breakeven as loss, paper tracker WIN_T1 frozen, WAITING_BREAKOUT never expired, Close-only stop checks, scan_date reset on sync | Honest backtest (was inflated) |
| 32 | **C&H Daily optimized** (720-combo sweep) | handle_bars 15→5, handle_depth_ratio 0.90→0.70. C&H expectancy -0.71%→+4.96% | Biggest single improvement |
| 33 | **Double Bottom optimized** (576-combo sweep) | windows, bottom_tol 0.10→0.05, min_peak 0.12→0.20, real volume. DB expectancy +0.81%→+1.46% | Tighter filter, higher quality |
| 34 | **Nifty SMA200 regime filter** (revised) | Scanner-us testing found RISK_OFF trades have PF 2.83 vs 1.33. Now warns but does NOT abort. | Informs user, doesn't block good trades |
| 35 | **Paper tracker: trailing stop after T1** | Breakeven stop after T1, High/Low checks, WAITING_BREAKOUT 30d expiry, scan_date preserved, 60d hold (was 45) | Protects profits, cleans stuck picks |
| 36 | **Honest backtest: +2.37% expectancy, PF 2.13** | v3.1 +2.03% was inflated by same-bar wicks. v3.2 +2.37% is honest AND higher due to optimization | Best version yet |
| 37 | **Out-of-sample validated on nifty200** | 1374 trades, +1.79% expectancy, PF 1.90. No overfitting. Wedge +1.48% OOS (was -1.70% in-sample) | Confidence in optimizations |

### scanner-us adoption testing (2026-09-05)

Validated improvements from scanner-us adoption testing (3 rounds, 500+ stocks):

| # | Change | Evidence | Impact |
|---|---|---|---|
| 26 | **Scan every 7 bars** (was 5) | nifty500: PF 1.56 vs 1.24 (+0.32). Confirmed on nifty200 and nifty500. | Biggest single improvement. Less noise, better signals. |
| 27 | **Max hold 60 days** (was 45) | nifty500: PF 1.39 vs 1.24 (+0.15). Avg win +8.48% vs +7.33%. | More time for swing trades to develop. |

**Rejected adoptions from scanner-us** (tested but NOT implemented):
- MTF confirmation: REJECT — NSE is mean-reverting, MTF filters out oversold bounces (-10pp WR)
- Inverse Head & Shoulders: REJECT — loses money on nifty200/500 (PF 0.70). Survivorship bias in backbone50 test.
- Double Top Breakout: REJECT — too few signals, loses money
- Regime filter: REJECT — RISK_OFF trades have PF 2.83 vs RISK_ON 1.33
- ATR 1.5x: NO CHANGE — no improvement over 2.0x on NSE
- Linear scoring: KEEP TIERED — tiered selects 2.7x better top trades

**Key lesson:** What works on US markets does NOT work on NSE. US is trending (institutional), NSE is mean-reverting (retail). Same filters have opposite effects.

Full test results: `scanner-us/SCANNER_COMPARISON.md`. Test scripts: `test_us_adoption.py`, `test_expanded.py`, `test_nifty500.py`.

### Backtest results (backbone50, 51 stocks, 2 years, min_score=40)

| Version | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | Max DD |
|---|---|---|---|---|---|---|---|
| **v3.2 (bug fixes + optimized)** | **438** | **56.6%** | **+7.91%** | **-4.85%** | **+2.37%** | **2.13** | **-48.7%** |
| v3.1 (pre-audit, has bugs) | 860 | 42.7% | +11.63% | -5.12% | +2.03% | 1.69 | -69.1% |

**Note:** The v3.1 +2.03% was inflated by same-bar wick captures and NEAR pre-breakout entries. The v3.2 +2.37% is honest — and higher because the C&H and DB optimizations more than recovered the honesty discount.

## What's new in v3.1 (2026-07-29)

| # | Change | Evidence | Impact |
|---|---|---|---|
| 14 | ATR multiplier 1.5x -> 2.0x | backbone50 sweep: PF 2.03 vs 1.80, maxDD -46.8% vs -66.7% | Fewer whipsaws |
| 15 | 8% max stop cap for ALL patterns | Monthly patterns had 15-25% structural stops | Risk capped |
| 16 | Monthly C&H NEAR threshold 20% -> 5% | Was surfacing stocks 20% below breakout | Actionable only |
| 17 | T1 target 60% -> 50% of measured move | Full move too ambitious for swings | Realistic targets |
| 18 | Max risk filter (10%) | Picks with >10% stop rejected | Quality filter |
| 19 | Max distance filter (8%) | NEAR/WATCH >8% from breakout rejected | Actionable only |
| 20 | R:R from breakout entry, not CMP | NEAR picks had misleading R:R | Accurate R:R |
| 21 | Wide-stop R:R penalty | R:R halved for >8% risk | Quality filter |
| 22 | Re-entry after whipsaw | 49.2% WR on re-entries (highest of any pattern) | Captures recoveries |
| 23 | Paper tracker: NEAR waits for breakout | Was 83% stop-out rate on NEAR picks | Proper entry timing |
| 24 | `--stocks` flag | Custom stock list scanning | Faster testing |
| 25 | Whipsaw analysis tool | 16.3% of SL exits would have hit T1 | Insight tool |

## What's new in v3 (vs v2)

All improvements driven by performance verification of 414 picks (May-Jul 2026):

| # | Improvement | Evidence | Impact |
|---|---|---|---|
| 1 | **ATR-based stop loss** (default) | v2 avg SL loss was -6.5%; earnings-scanner proved -3% stops work | Tighter stops = smaller losses |
| 2 | **Double Bottom promoted** | 100% win rate (11W/0L) across scanners | Score bonus 18 -> 28 |
| 3 | **Channel Breakout tightened** | 24% win rate — was dragging performance | Volume gate 1.3x -> 1.5x, RSI < 75, R:R >= 1.5 |
| 4 | **Cup & Handle (Weekly) promoted** | 50% win rate in scanner/ | Score bonus 25 -> 28 |
| 5 | **Price range filter** | Retail-friendly high-momentum stocks | `--min-price 100 --max-price 400` |
| 6 | **Self-contained sector rotation** | No dependency on scanner/ | `utils/sector_rotation_v3.py` |
| 7 | **Bearish / short mode** | NSE Heat Map strategy: find weak sectors, short weakest stocks | `--bearish` flag |
| 8 | **requirements.txt** | Was missing | Reproducible installs |

## Quick start

```powershell
pip install -r requirements.txt

# Full weekly scan (top 30 setups)
python scanner.py

# Top 50, min score 50
python scanner.py --top 50 --min-score 50

# Retail filter: only stocks between 100-400 Rs
python scanner.py --min-price 100 --max-price 400

# Original v2 stop loss (wider, for comparison)
python scanner.py --sl-mode original

# Bearish scan: find short setups in weak sectors
python scanner.py --bearish

# Quick test (50 stocks only)
python scanner.py --test

# Daily morning scan (volume surges + hot sectors)
python daily_scan.py --top 15

# Daily scan with price filter
python daily_scan.py --min-price 100 --max-price 400

# Daily bearish scan
python daily_scan.py --bearish

# Weekly scan + charts + Telegram
.\run_weekly.bat

# Daily scan
.\Daily Scan.bat
```

## CLI options

### scanner.py
| Flag | Default | Description |
|---|---|---|
| `--top` | 30 | Number of top setups to show |
| `--min-score` | 50 | Minimum score (0-100) |
| `--workers` | 4 | Parallel data fetch workers |
| `--sl-mode` | atr | Stop loss: `atr` (tighter) or `original` (v2) |
| `--min-price` | None | Minimum stock price (e.g. 100) |
| `--max-price` | None | Maximum stock price (e.g. 400) |
| `--bearish` | False | Scan for short setups in weak sectors |
| `--test` | False | Quick test on 50 stocks |

### daily_scan.py
| Flag | Default | Description |
|---|---|---|
| `--top` | 15 | Number of stocks to show per category |
| `--sector` | None | Force a specific sector (METAL/AUTO/BANK/IT etc) |
| `--sectors` | 2 | Number of hot/weak sectors to include |
| `--min-price` | None | Minimum stock price |
| `--max-price` | None | Maximum stock price |
| `--bearish` | False | Find weak sectors + short candidates |

## Architecture

```
scanner-v3/
  scanner.py              # Main weekly scanner (v3 engine)
  daily_scan.py           # Daily morning scanner (volume + sectors)
  gen_charts.py           # Chart generator
  telegram_notify.py      # Telegram alerts
  config/
    settings.py           # Configuration constants
  data/
    loader.py             # NSE data fetcher (jugaad-data + yfinance fallback)
    nse_eq.py             # NSE EQ universe loader
  patterns/
    cup_handle.py         # Cup & Handle (daily + weekly, diagonal neckline)
    cup_handle_monthly.py # Cup & Handle (monthly timeframe)
    double_bottom.py      # Double Bottom (100% win rate — promoted)
    channel.py            # Channel Breakout (v3: tightened criteria)
    wedge.py              # Descending Wedge
    breakout.py           # Resistance Breakout
    break_retest.py       # Break & Retest
    triangle.py           # Ascending/Symmetrical Triangle
    darvas_box.py         # Darvas Box
    flags.py              # Bullish Flag / Pennant
    sr_levels.py          # Support & Resistance levels
    retest.py             # Retest breakout
    compression.py        # Compression / Squeeze
  utils/
    sector_rotation_v3.py # Sector rotation (self-contained, bullish + bearish)
  results/                # CSV output (auto-created)
```

## Performance baseline (scanner-v2, May-Jul 2026)

| Metric | Value |
|---|---|
| Total picks | 414 |
| Closed trades | 97 |
| Win rate | 35.1% |
| Avg win | +19.7% |
| Avg loss | -6.5% |
| Risk:Reward | 3.04 |
| **Expectancy/trade** | **+2.7%** |

v3 targets: tighter SLs should reduce avg loss from -6.5% to ~-4%, Double Bottom promotion should increase win rate, Channel Breakout tightening should remove low-quality picks.
