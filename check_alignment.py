"""Check if scanner HOT sectors align with live sector rotation"""
import sys
sys.path.insert(0, '.')
from utils.sector_rotation_v3 import get_hot_sectors, get_weak_sectors, get_sector_heat

print('=' * 80)
print('SCANNER ALIGNMENT CHECK')
print('=' * 80)
print()

# What the scanner thinks are HOT
hot = get_hot_sectors(top_n=3)
weak = get_weak_sectors()

print('SCANNER HOT SECTORS (top 3 by 20D performance):')
for s in hot:
    print(f'  - {s}')
print()

print('SCANNER WEAK SECTORS (negative 20D performance):')
for s in weak:
    print(f'  - {s}')
print()

# What we just analyzed
heat = get_sector_heat()
sorted_sectors = sorted(heat.items(), key=lambda x: x[1]['perf_20d'], reverse=True)

print('LIVE SECTOR ROTATION (from sector analysis):')
print()
print('Top 5 (best 20D performance):')
for i, (name, data) in enumerate(sorted_sectors[:5], 1):
    sig = data['signal']
    p5 = data['perf_5d']
    p20 = data['perf_20d']
    print(f'  {i}. {name} ({sig}) - 5D: {p5:+.1f}%, 20D: {p20:+.1f}%')
print()

print('Bottom 5 (worst 20D performance):')
for i, (name, data) in enumerate(sorted_sectors[-5:], 1):
    sig = data['signal']
    p5 = data['perf_5d']
    p20 = data['perf_20d']
    print(f'  {i}. {name} ({sig}) - 5D: {p5:+.1f}%, 20D: {p20:+.1f}%')
print()

# Check alignment
print('=' * 80)
print('ALIGNMENT VERIFICATION')
print('=' * 80)
print()

top3_actual = [name for name, _ in sorted_sectors[:3]]
print(f'Scanner says HOT: {hot}')
print(f'Live top 3:       {top3_actual}')
print()

if set(hot) == set(top3_actual):
    print('[OK] PERFECT ALIGNMENT - Scanner HOT sectors match live top 3')
else:
    print('[!!] MISALIGNMENT DETECTED')
    print()
    print('Difference:')
    only_scanner = set(hot) - set(top3_actual)
    only_live = set(top3_actual) - set(hot)
    if only_scanner:
        print(f'  Scanner has but shouldnt: {only_scanner}')
    if only_live:
        print(f'  Missing from scanner:     {only_live}')
    print()
    print('NOTE: This is OK - scanner uses top_n=3 of RISING sectors only.')
    print('Live top 3 may include COOLING sectors (like Realty).')

print()
print('=' * 80)
print('SCANNER LOGIC EXPLANATION')
print('=' * 80)
print()
print('get_hot_sectors() returns top N sectors with signal = RISING or BOOM')
print('ranked by 20D performance.')
print()
print('It filters OUT:')
print('  - COOLING sectors (5D negative, 20D positive)')
print('  - WEAK sectors (20D negative)')
print()
print('So HOT sectors = BOOM + RISING only, sorted by 20D perf.')
print()

# Show what scanner actually returns
print('SCANNER HOT SECTORS (BOOM/RISING only):')
boom_rising = [(name, data) for name, data in sorted_sectors 
               if data['signal'] in ['BOOM', 'RISING']]
for i, (name, data) in enumerate(boom_rising[:5], 1):
    sig = data['signal']
    p20 = data['perf_20d']
    is_hot = 'HOT' if name in hot else ''
    print(f'  {i}. {name} ({sig}, {p20:+.1f}%) {is_hot}')
