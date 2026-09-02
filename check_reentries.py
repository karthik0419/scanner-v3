"""Check RE-ENTRY trades (stocks that hit SL but recovered)"""
import pandas as pd
from utils.sector_rotation_v3 import get_stock_sector

# Load tracker
df = pd.read_csv('results/paper_tracker.csv')

# Find RE-ENTRY trades
re_entries = df[df['pattern'].str.contains('RE-ENTRY', na=False)]

print("=" * 80)
print("RE-ENTRY TRADES - Stocks that Hit SL but Recovered")
print("=" * 80)
print(f"\nTotal RE-ENTRY trades: {len(re_entries)}")
print()

if len(re_entries) > 0:
    print(f"{'Symbol':<20} {'Pattern':<35} {'Sector':<15} {'P&L%':>7} {'Status':<12}")
    print("-" * 100)
    
    for _, row in re_entries.iterrows():
        sector = get_stock_sector(row['symbol'])
        print(f"{row['symbol']:<20} {row['pattern']:<35} {sector:<15} {row['current_pnl_pct']:>6.2f}% {row['current_status']:<12}")
    
    # Stats
    print("\n" + "=" * 80)
    print("RE-ENTRY STATISTICS")
    print("=" * 80)
    
    open_re = re_entries[re_entries['current_status'] == 'OPEN']
    closed_re = re_entries[re_entries['current_status'].isin(['LOSS', 'WIN_T2', 'TIME_EXIT'])]
    
    print(f"Open: {len(open_re)}")
    print(f"Closed: {len(closed_re)}")
    
    if len(open_re) > 0:
        print(f"\nOpen RE-ENTRIES avg P&L: {open_re['current_pnl_pct'].mean():.2f}%")
        profitable = len(open_re[open_re['current_pnl_pct'] > 0])
        print(f"Profitable: {profitable}/{len(open_re)} ({profitable/len(open_re)*100:.1f}%)")
    
    if len(closed_re) > 0:
        print(f"\nClosed RE-ENTRIES avg P&L: {closed_re['current_pnl_pct'].mean():.2f}%")
        wins = len(closed_re[closed_re['current_pnl_pct'] > 0])
        print(f"Win rate: {wins}/{len(closed_re)} ({wins/len(closed_re)*100:.1f}%)")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print("\nRE-ENTRY feature catches whipsaws - stocks that:")
    print("  1. Hit stop loss (got shaken out)")
    print("  2. Recovered above breakout within 30 days")
    print("  3. Re-entered with tight 2% stop")
    print()
    print("Expected: 49.2% win rate (highest of any pattern)")
    print(f"Actual: {(len(re_entries[re_entries['current_pnl_pct'] > 0]) / len(re_entries) * 100):.1f}% profitable" if len(re_entries) > 0 else "N/A")
    
else:
    print("No RE-ENTRY trades found.")
    print()
    print("This means:")
    print("  - No stocks have hit SL and recovered yet")
    print("  - Or tracker hasn't been updated to check for re-entries")
    print()
    print("To enable re-entry checking:")
    print("  python paper_tracker.py update")

print("\n" + "=" * 80)

# Also check for stocks that hit SL and might re-enter
print("\nCHECKING FOR POTENTIAL RE-ENTRIES...")
print("=" * 80)

# Get all LOSS trades
losses = df[df['current_status'] == 'LOSS']
print(f"\nTotal LOSS trades: {len(losses)}")
print("(These are candidates for re-entry if they recover above breakout)")
print()

# Show recent losses (last 10)
print("Recent LOSS trades (potential re-entry candidates):")
print(f"{'Symbol':<20} {'Pattern':<30} {'Breakout':>10} {'Exit P&L%':>10}")
print("-" * 80)

for _, row in losses.tail(10).iterrows():
    breakout = row.get('breakout_level', 0)
    print(f"{row['symbol']:<20} {row['pattern']:<30} {breakout:>10.2f} {row['current_pnl_pct']:>9.2f}%")

print("\nNote: Run 'python paper_tracker.py update' to check if any have recovered")
