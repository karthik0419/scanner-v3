"""Show today's top picks with sectors"""
import pandas as pd
from utils.sector_rotation_v3 import get_stock_sector
from utils.regime import get_market_regime

# Load latest scan
df = pd.read_csv('results/v3_2026-08-27_all.csv')

# Get market regime
regime = get_market_regime()
hot_sectors = regime.get('strong_sectors', ['Pharma', 'IT', 'FMCG']) if regime else ['Pharma', 'IT', 'FMCG']

print("=" * 100)
print("TOP PICKS TODAY (27-Aug-2026)")
print("=" * 100)

# Get top 15 by score
top = df.nlargest(15, 'score')

print(f"\n{'Symbol':<15} {'Pattern':<20} {'Score':<6} {'Status':<10} {'Sector':<15} {'R:R':<6} {'Upside':<8} {'HOT?'}")
print("-" * 100)

buyable_today = []

for _, row in top.iterrows():
    sector = get_stock_sector(row['symbol'])
    is_hot = 'YES' if sector in hot_sectors else 'NO'
    
    print(f"{row['symbol']:<15} {row['pattern']:<20} {row['score']:<6.1f} {row['status']:<10} {sector:<15} {row['rr']:<6.2f} {row['upside_%']:<8.1f}% {is_hot}")
    
    # Buyable criteria: BREAKOUT status + score >= 70 + HOT sector
    if row['status'] == 'BREAKOUT' and row['score'] >= 70 and sector in hot_sectors:
        buyable_today.append({
            'symbol': row['symbol'],
            'sector': sector,
            'pattern': row['pattern'],
            'score': row['score'],
            'cmp': row['cmp'],
            'breakout': row['breakout'],
            'stop': row['stop_loss'],
            'target1': row['target_1'],
            'target2': row['target_2'],
            'rr': row['rr'],
            'upside': row['upside_%']
        })

print("\n" + "=" * 100)
print("BUYABLE TODAY (BREAKOUT + Score >= 70 + HOT Sector)")
print("=" * 100)

if buyable_today:
    print(f"\nFound {len(buyable_today)} stocks you can BUY TODAY:\n")
    
    for i, stock in enumerate(buyable_today, 1):
        print(f"{i}. {stock['symbol']} ({stock['sector']} - HOT)")
        print(f"   Pattern: {stock['pattern']}")
        print(f"   Score: {stock['score']:.1f}")
        print(f"   CMP: Rs {stock['cmp']:.2f}")
        print(f"   Entry: Rs {stock['breakout']:.2f} (BREAKOUT - can enter now)")
        print(f"   Stop: Rs {stock['stop']:.2f} ({((stock['cmp'] - stock['stop']) / stock['cmp'] * 100):.1f}% risk)")
        print(f"   Target 1: Rs {stock['target1']:.2f} (+{((stock['target1'] - stock['cmp']) / stock['cmp'] * 100):.1f}%)")
        print(f"   Target 2: Rs {stock['target2']:.2f} (+{((stock['target2'] - stock['cmp']) / stock['cmp'] * 100):.1f}%)")
        print(f"   R:R: {stock['rr']:.2f}")
        print()
else:
    print("\nNO BUYABLE STOCKS TODAY")
    print("\nReasons:")
    print("  - No BREAKOUT stocks in HOT sectors (Pharma, IT, FMCG)")
    print("  - Most picks are NEAR/WATCH (wait for breakout)")
    print("  - Market is BEAR - limited opportunities")
    print("\nRECOMMENDATION: STAY IN CASH")

print("=" * 100)
print(f"Market Regime: {regime['status'] if regime else 'Unknown'}")
print(f"HOT Sectors: {', '.join(hot_sectors)}")
print("=" * 100)
