"""
Real-time regime filter test: Can we detect bull/bear in real-time using Nifty index?
If yes, combine with sector filter for a tradeable strategy.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
from utils.sector_rotation_v3 import get_stock_sector

# Load trades
df = pd.read_csv('results/portfolio_multi_20260803.csv')
df['entry_date'] = pd.to_datetime(df['entry_date']).dt.tz_localize(None)

# Add sector
sectors = {}
for sym in df['symbol'].unique():
    sectors[sym] = get_stock_sector(sym)
df['sector'] = df['symbol'].map(sectors)

# Fetch Nifty 50 for regime detection
print("Fetching Nifty 50 for regime detection...")
nifty = yf.Ticker('^NSEI').history(period='6y')
if nifty.index.tz is not None:
    nifty.index = nifty.index.tz_localize(None)
nifty = nifty.dropna()

# Real-time regime: Nifty above/below 50-day SMA
nifty['sma50'] = nifty['Close'].rolling(50).mean()
nifty['sma200'] = nifty['Close'].rolling(200).mean()
nifty['regime_sma'] = np.where(nifty['Close'] > nifty['sma50'], 'BULL', 'BEAR')
nifty['regime_sma200'] = np.where((nifty['Close'] > nifty['sma50']) & (nifty['Close'] > nifty['sma200']), 'BULL', 'BEAR')

# Map regime to trade dates
def get_regime(date, mode='sma'):
    # Use the regime from the PRIOR trading day (no look-ahead)
    mask = nifty.index <= date
    if mask.sum() == 0:
        return 'UNKNOWN'
    col = 'regime_sma' if mode == 'sma' else 'regime_sma200'
    return nifty.loc[mask, col].iloc[-1]

df['regime_sma'] = df['entry_date'].apply(lambda d: get_regime(d, 'sma'))
df['regime_sma200'] = df['entry_date'].apply(lambda d: get_regime(d, 'sma200'))

print(f"\nRegime distribution (SMA50): {df['regime_sma'].value_counts().to_dict()}")
print(f"Regime distribution (SMA50+SMA200): {df['regime_sma200'].value_counts().to_dict()}")

# Top 5 sectors
top5 = ['Auto', 'Media', 'Telecom', 'Energy', 'Chemicals']

# Test combinations
print("\n" + "=" * 80)
print("  REAL-TIME FILTER COMBINATIONS (no look-ahead bias)")
print("=" * 80)

def simulate_portfolio(trades_df, label):
    """Simple portfolio sim: Rs 50k, 4 positions, proportional scaling."""
    cap = 50000
    active = []
    trades = trades_df.sort_values('entry_date').to_dict('records')
    for t in trades:
        # Remove exited positions
        exit_d = pd.to_datetime(t['exit_date'])
        entry_d = pd.to_datetime(t['entry_date'])
        active = [p for p in active if p['exit_date'] >= entry_d]
        if len(active) >= 4:
            continue
        pos = cap / 4
        shares = int(pos / t['entry_price'])
        if shares < 1:
            continue
        cost = shares * t['entry_price']
        scale = cost / t['cost']
        cap += t['net_pnl'] * scale
        active.append({'exit_date': exit_d})
    ret = ((cap / 50000) - 1) * 100
    wr = (trades_df['net_pnl'] > 0).mean() * 100
    avg = trades_df['net_pnl'].mean()
    print(f"  {label}")
    print(f"    Trades: {len(trades_df)}  WR: {wr:.1f}%  Avg: {avg:+.2f}  Final: Rs {cap:,.0f}  Return: {ret:+.1f}%")
    return cap, ret

# Baseline
simulate_portfolio(df, "BASELINE (no filters)")

# Sector only
simulate_portfolio(df[df['sector'].isin(top5)], "Top 5 sectors only")

# Regime only (SMA50)
simulate_portfolio(df[df['regime_sma'] == 'BULL'], "BULL regime only (Nifty > SMA50)")

# Regime only (SMA50+SMA200)
simulate_portfolio(df[df['regime_sma200'] == 'BULL'], "BULL regime only (Nifty > SMA50 & SMA200)")

# Sector + Regime
simulate_portfolio(df[df['sector'].isin(top5) & (df['regime_sma'] == 'BULL')],
                   "Top 5 sectors + BULL regime (SMA50)")
simulate_portfolio(df[df['sector'].isin(top5) & (df['regime_sma200'] == 'BULL')],
                   "Top 5 sectors + BULL regime (SMA50+SMA200)")

# Top 3 sectors
top3 = ['Auto', 'Media', 'Telecom']
simulate_portfolio(df[df['sector'].isin(top3) & (df['regime_sma'] == 'BULL')],
                   "Top 3 sectors + BULL regime (SMA50)")
simulate_portfolio(df[df['sector'].isin(top3) & (df['regime_sma200'] == 'BULL')],
                   "Top 3 sectors + BULL regime (SMA50+SMA200)")

# Exclude worst sectors + regime
worst = ['Infra', 'Realty', 'Textiles', 'Banking', 'Metals']
simulate_portfolio(df[~df['sector'].isin(worst) & (df['regime_sma'] == 'BULL')],
                   "Exclude worst 5 + BULL regime (SMA50)")
simulate_portfolio(df[~df['sector'].isin(worst) & (df['regime_sma200'] == 'BULL')],
                   "Exclude worst 5 + BULL regime (SMA50+SMA200)")

# Consistent sectors only
consistent = ['Auto', 'FMCG', 'Pharma', 'Telecom']
simulate_portfolio(df[df['sector'].isin(consistent) & (df['regime_sma'] == 'BULL')],
                   "Consistent 4 sectors + BULL regime (SMA50)")
simulate_portfolio(df[df['sector'].isin(consistent) & (df['regime_sma200'] == 'BULL')],
                   "Consistent 4 sectors + BULL regime (SMA50+SMA200)")

# CAGR calculation
print("\n" + "=" * 80)
print("  CAGR COMPARISON (5 years)")
print("=" * 80)
years = 5
fd_cagr = 7.0
combos = [
    ("Baseline (no filter)", df),
    ("Top 5 sectors", df[df['sector'].isin(top5)]),
    ("BULL regime (SMA50)", df[df['regime_sma'] == 'BULL']),
    ("Top 5 + BULL (SMA50)", df[df['sector'].isin(top5) & (df['regime_sma'] == 'BULL')]),
    ("Top 5 + BULL (SMA50+200)", df[df['sector'].isin(top5) & (df['regime_sma200'] == 'BULL')]),
    ("Top 3 + BULL (SMA50)", df[df['sector'].isin(top3) & (df['regime_sma'] == 'BULL')]),
    ("Top 3 + BULL (SMA50+200)", df[df['sector'].isin(top3) & (df['regime_sma200'] == 'BULL')]),
    ("Consistent 4 + BULL (SMA50)", df[df['sector'].isin(consistent) & (df['regime_sma'] == 'BULL')]),
    ("Exclude worst 5 + BULL (SMA50)", df[~df['sector'].isin(worst) & (df['regime_sma'] == 'BULL')]),
]

print(f"  {'Config':<35s}  {'Trades':>7s}  {'Final':>12s}  {'Return':>8s}  {'CAGR':>8s}")
for label, subset in combos:
    if len(subset) == 0:
        continue
    cap = 50000
    active = []
    for t in subset.sort_values('entry_date').to_dict('records'):
        exit_d = pd.to_datetime(t['exit_date'])
        entry_d = pd.to_datetime(t['entry_date'])
        active = [p for p in active if p['exit_date'] >= entry_d]
        if len(active) >= 4: continue
        pos = cap / 4
        shares = int(pos / t['entry_price'])
        if shares < 1: continue
        cost = shares * t['entry_price']
        cap += t['net_pnl'] * (cost / t['cost'])
        active.append({'exit_date': exit_d})
    ret = ((cap / 50000) - 1) * 100
    cagr = (((cap / 50000) ** (1/years)) - 1) * 100
    print(f"  {label:<35s}  {len(subset):>7d}  Rs {cap:>9.0f}  {ret:>+7.1f}%  {cagr:>+7.1f}%")

print(f"  {'Bank FD (7% annual)':<35s}  {'':>7s}  Rs {50000*1.35:>9.0f}  {'+35.0%':>8s}  {'7.0%':>8s}")

# Quarterly breakdown for best combo
print("\n" + "=" * 80)
print("  BEST COMBO QUARTERLY BREAKDOWN: Top 5 + BULL (SMA50)")
print("=" * 80)
best = df[df['sector'].isin(top5) & (df['regime_sma'] == 'BULL')]
best_q = best.groupby('period').agg(
    trades=('net_pnl', 'count'),
    wins=('net_pnl', lambda x: (x > 0).sum()),
    pnl=('net_pnl', 'sum'),
).reset_index()
for _, r in best_q.iterrows():
    print(f"  {str(r['period']):>10s}  {r['trades']:>3d} trades  {r['wins']:>2d}W  Rs {r['pnl']:>+9.2f}")
