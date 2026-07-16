# Swing Scanner v3 — Production

NSE swing trading setup scanner. Built on scanner-v2 (proven +2.7% expectancy per trade, 35% win rate, 3:1 R:R over 97 closed trades).

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
