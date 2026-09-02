"""
Sector Breakout Analysis - Identify sectors likely to break out
"""
import sys
sys.path.insert(0, '.')
from utils.sector_rotation_v3 import get_sector_heat, get_hot_sectors, get_weak_sectors

print('=' * 80)
print('NIFTY SECTOR ANALYSIS - Breakout Candidates')
print('Date: 2026-08-28')
print('=' * 80)
print()

# Get sector strength rankings
sectors = get_sector_heat()

# Sort by performance (perf_20d desc)
sorted_sectors = sorted(sectors.items(), key=lambda x: x[1]['perf_20d'], reverse=True)

print('SECTOR HEAT MAP (sorted by 20-day performance)')
print('-' * 80)
print(f"{'Rank':<6} {'Sector':<25} {'Signal':<12} {'5D%':<8} {'20D%':<8} {'Breakout Potential'}")
print('-' * 80)

for i, (name, data) in enumerate(sorted_sectors, 1):
    signal = data['signal']
    perf_5d = data['perf_5d']
    perf_20d = data['perf_20d']
    
    # Determine breakout potential based on rank and signal
    if signal == 'BOOM':
        potential = '[***] VERY HIGH - explosive move'
    elif signal == 'RISING' and i <= 5:
        potential = '[ **] HIGH - strong momentum'
    elif signal == 'RISING' and i <= 10:
        potential = '[  *] MEDIUM - uptrend confirmed'
    elif signal == 'RISING':
        potential = '[  -] LOW - lagging RISING'
    elif signal == 'COOLING':
        potential = '[  ?] WAIT - losing steam'
    elif signal == 'WEAK':
        potential = '[  X] AVOID - downtrend'
    else:
        potential = '[  -] NEUTRAL'
    
    print(f"{i:<6} {name:<25} {signal:<12} {perf_5d:>6.1f}% {perf_20d:>6.1f}% {potential}")

print()
print('=' * 80)
print('TOP 5 BREAKOUT CANDIDATES (best momentum)')
print('=' * 80)
print()

top5 = sorted_sectors[:5]
for i, (name, data) in enumerate(top5, 1):
    rank = i
    print(f"{i}. {name} (rank #{rank})")
    print(f"   Signal: {data['signal']} | 5D: {data['perf_5d']:+.1f}% | 20D: {data['perf_20d']:+.1f}%")
    
    if data['signal'] == 'BOOM':
        thesis = 'Explosive move - strong short-term + long-term momentum'
    elif data['signal'] == 'RISING':
        thesis = 'Steady uptrend - stocks here likely to lead next leg up'
    elif data['signal'] == 'COOLING':
        thesis = 'Topping out - take profits, dont add new'
    else:
        thesis = 'Weak - avoid'
    
    print(f"   Thesis: {thesis}")
    print()

print('=' * 80)
print('BOTTOM 5 SECTORS TO AVOID (weakest)')
print('=' * 80)
print()

bottom5 = sorted_sectors[-5:]
for i, (name, data) in enumerate(bottom5, 1):
    rank = len(sorted_sectors) - 5 + i
    print(f"{i}. {name} (rank #{rank})")
    print(f"   Signal: {data['signal']} | 5D: {data['perf_5d']:+.1f}% | 20D: {data['perf_20d']:+.1f}%")
    print(f"   Thesis: Weak downtrend - exit positions, avoid new entries")
    print()

print('=' * 80)
print('ACTIONABLE STRATEGY')
print('=' * 80)
print()
print("BUY: Focus on top 5 RISING sectors for new positions")
print("HOLD: Existing positions in RISING sectors (rank 6-15)")
print("EXIT: Positions in WEAK sectors (especially bottom 10)")
print()
