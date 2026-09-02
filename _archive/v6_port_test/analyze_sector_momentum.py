"""Analyze 5-year momentum trades by sector to find if sector filtering helps."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from utils.sector_rotation_v3 import get_stock_sector

df = pd.read_csv('results/portfolio_multi_20260803.csv')
print(f"Total trades: {len(df)}")
print()

# Add sector to each trade
sectors = {}
for sym in df['symbol'].unique():
    sec = get_stock_sector(sym)
    sectors[sym] = sec

df['sector'] = df['symbol'].map(sectors)

# Sector breakdown
print("=" * 80)
print("  SECTOR BREAKDOWN (5-year momentum trades, MULTI mode)")
print("=" * 80)
print(f"  {'Sector':>16s}  {'Trades':>7s}  {'Win%':>6s}  {'Avg P&L':>8s}  {'Total P&L':>12s}  {'Avg Win':>8s}  {'Avg Loss':>9s}")
print("-" * 80)

sector_stats = df.groupby('sector').agg(
    trades=('net_pnl', 'count'),
    win_rate=('net_pnl', lambda x: (x > 0).mean() * 100),
    avg_pnl=('net_pnl', 'mean'),
    total_pnl=('net_pnl', 'sum'),
    avg_win=('net_pnl', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
    avg_loss=('net_pnl', lambda x: x[x <= 0].mean() if (x <= 0).any() else 0),
).reset_index().sort_values('total_pnl', ascending=False)

for _, r in sector_stats.iterrows():
    print(f"  {r['sector']:>16s}  {r['trades']:>7d}  {r['win_rate']:>5.1f}%  {r['avg_pnl']:>+7.2f}  Rs {r['total_pnl']:>+9.2f}  {r['avg_win']:>+7.2f}  {r['avg_loss']:>+8.2f}")

print()
print(f"  PROFITABLE sectors: {len(sector_stats[sector_stats['total_pnl'] > 0])}")
print(f"  LOSING sectors:     {len(sector_stats[sector_stats['total_pnl'] <= 0])}")
print()

# What if we only traded the top sectors?
print("=" * 80)
print("  WHAT IF: Only trade top N sectors?")
print("=" * 80)

for n in [3, 5, 8, 10]:
    top_sectors = sector_stats.head(n)['sector'].tolist()
    filtered = df[df['sector'].isin(top_sectors)]
    if len(filtered) == 0:
        continue
    total_pnl = filtered['net_pnl'].sum()
    wr = (filtered['net_pnl'] > 0).mean() * 100
    avg_pnl = filtered['net_pnl'].mean()
    # Simulate with Rs 50k capital, 4 positions
    cap = 50000
    for _, t in filtered.iterrows():
        # position size = cap/4
        pos = cap / 4
        shares = int(pos / t['entry_price'])
        if shares < 1:
            continue
        cost = shares * t['entry_price']
        # scale net_pnl proportionally
        scale = cost / t['cost']
        cap += t['net_pnl'] * scale
    ret = ((cap / 50000) - 1) * 100
    print(f"  Top {n:>2d} sectors: {len(filtered):>4d} trades  WR={wr:.1f}%  avg={avg_pnl:+.2f}  final=Rs {cap:,.0f}  return={ret:+.1f}%")
    print(f"           Sectors: {', '.join(top_sectors)}")

print()

# What if we EXCLUDED the worst sectors?
print("=" * 80)
print("  WHAT IF: Exclude worst N sectors?")
print("=" * 80)

for n in [3, 5, 8]:
    worst_sectors = sector_stats.tail(n)['sector'].tolist()
    filtered = df[~df['sector'].isin(worst_sectors)]
    if len(filtered) == 0:
        continue
    total_pnl = filtered['net_pnl'].sum()
    wr = (filtered['net_pnl'] > 0).mean() * 100
    avg_pnl = filtered['net_pnl'].mean()
    cap = 50000
    for _, t in filtered.iterrows():
        pos = cap / 4
        shares = int(pos / t['entry_price'])
        if shares < 1:
            continue
        cost = shares * t['entry_price']
        scale = cost / t['cost']
        cap += t['net_pnl'] * scale
    ret = ((cap / 50000) - 1) * 100
    print(f"  Exclude worst {n}: {len(filtered):>4d} trades  WR={wr:.1f}%  avg={avg_pnl:+.2f}  final=Rs {cap:,.0f}  return={ret:+.1f}%")
    print(f"           Excluded: {', '.join(worst_sectors)}")

print()

# Sector + market regime (bull vs bear)
print("=" * 80)
print("  SECTOR PERFORMANCE BY YEAR (market regime analysis)")
print("=" * 80)

df['year'] = pd.to_datetime(df['entry_date']).dt.year
pivot = df.pivot_table(values='net_pnl', index='sector', columns='year', aggfunc='sum', fill_value=0)
print(pivot.to_string())
print()

# Which sectors are consistently profitable?
print("=" * 80)
print("  CONSISTENTLY PROFITABLE SECTORS (profitable in most years)")
print("=" * 80)
yearly_profitable = (pivot > 0).sum(axis=1)
consistent = yearly_profitable[yearly_profitable >= 3].index.tolist()
print(f"  Profitable in 3+ years: {consistent}")
for sec in consistent:
    row = pivot.loc[sec]
    print(f"    {sec:>16s}: " + "  ".join(f"{y}:{row[y]:+.0f}" for y in pivot.columns))

print()
# Which sectors work in bull vs bear?
print("=" * 80)
print("  SECTOR + QUARTERLY REGIME")
print("=" * 80)
# Define bull/bear by overall quarterly P&L
q_pnl = df.groupby('period')['net_pnl'].sum()
bull_quarters = q_pnl[q_pnl > 0].index.tolist()
bear_quarters = q_pnl[q_pnl <= 0].index.tolist()
print(f"  Bull quarters: {bull_quarters}")
print(f"  Bear quarters: {bear_quarters}")
print()

for sec in sector_stats.head(10)['sector']:
    sec_trades = df[df['sector'] == sec]
    bull = sec_trades[sec_trades['period'].isin(bull_quarters)]
    bear = sec_trades[sec_trades['period'].isin(bear_quarters)]
    bull_pnl = bull['net_pnl'].sum() if len(bull) > 0 else 0
    bear_pnl = bear['net_pnl'].sum() if len(bear) > 0 else 0
    bull_wr = (bull['net_pnl'] > 0).mean() * 100 if len(bull) > 0 else 0
    bear_wr = (bear['net_pnl'] > 0).mean() * 100 if len(bear) > 0 else 0
    print(f"  {sec:>16s}  Bull: {len(bull):>3d}t  WR={bull_wr:>5.1f}%  P&L={bull_pnl:>+8.0f}  |  Bear: {len(bear):>3d}t  WR={bear_wr:>5.1f}%  P&L={bear_pnl:>+8.0f}")

print()

# What if we only trade in bull quarters + top sectors?
print("=" * 80)
print("  ULTIMATE FILTER: Top 5 sectors + Bull quarters only")
print("=" * 80)
top5 = sector_stats.head(5)['sector'].tolist()
ultimate = df[df['sector'].isin(top5) & df['period'].isin(bull_quarters)]
if len(ultimate) > 0:
    wr = (ultimate['net_pnl'] > 0).mean() * 100
    avg = ultimate['net_pnl'].mean()
    total = ultimate['net_pnl'].sum()
    cap = 50000
    for _, t in ultimate.iterrows():
        pos = cap / 4
        shares = int(pos / t['entry_price'])
        if shares < 1: continue
        cost = shares * t['entry_price']
        cap += t['net_pnl'] * (cost / t['cost'])
    ret = ((cap/50000)-1)*100
    print(f"  Trades: {len(ultimate)}  WR: {wr:.1f}%  Avg: {avg:+.2f}  Total P&L: Rs {total:,.0f}")
    print(f"  Simulated final capital: Rs {cap:,.0f}  Return: {ret:+.1f}%")
    print(f"  Sectors: {top5}")
else:
    print("  No trades match this filter")
