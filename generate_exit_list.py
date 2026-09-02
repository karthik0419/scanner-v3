"""Generate exit list for weak sector trades"""
import pandas as pd
from utils.sector_rotation_v3 import get_stock_sector

# Load tracker
df = pd.read_csv('results/paper_tracker.csv')

# Get open trades
open_trades = df[df['current_status'] == 'OPEN']

# HOT sectors (from regime)
hot_sectors = ['Pharma', 'IT', 'FMCG']

# Build exit list
exit_list = []
keep_list = []

for _, row in open_trades.iterrows():
    sym = row['symbol']
    sector = get_stock_sector(sym)
    pnl = row['current_pnl_pct']
    
    # Exit criteria: Weak sector + negative P&L
    if sector not in hot_sectors and pnl < 0:
        exit_list.append({
            'symbol': sym,
            'sector': sector,
            'pnl': pnl,
            'entry': row['entry_price'],
            'current': row['current_price'],
            'pattern': row['pattern']
        })
    else:
        keep_list.append({
            'symbol': sym,
            'sector': sector,
            'pnl': pnl
        })

# Sort by P&L (worst first)
exit_list.sort(key=lambda x: x['pnl'])

print("=" * 80)
print("EXIT LIST - Weak Sector Trades with Losses")
print("=" * 80)
print(f"\n{'Symbol':<20} {'Sector':<15} {'Entry':>8} {'Current':>8} {'P&L%':>7}  {'Pattern'}")
print("-" * 80)

for trade in exit_list:
    print(f"{trade['symbol']:<20} {trade['sector']:<15} {trade['entry']:>8.2f} "
          f"{trade['current']:>8.2f} {trade['pnl']:>6.2f}%  {trade['pattern']}")

print("\n" + "=" * 80)
print(f"Total trades to EXIT: {len(exit_list)}")
print(f"Total loss if exited now: {sum([t['pnl'] for t in exit_list]):.2f}%")
print(f"Avg loss per trade: {sum([t['pnl'] for t in exit_list]) / len(exit_list):.2f}%" if exit_list else "N/A")
print("=" * 80)

print("\n" + "=" * 80)
print("KEEP LIST - HOT Sector Trades OR Profitable Weak Sector Trades")
print("=" * 80)
print(f"Total trades to KEEP: {len(keep_list)}")
print(f"Avg P&L: {sum([t['pnl'] for t in keep_list]) / len(keep_list):.2f}%" if keep_list else "N/A")
print("=" * 80)

# Save exit list to CSV
if exit_list:
    exit_df = pd.DataFrame(exit_list)
    exit_df.to_csv('results/exit_list.csv', index=False)
    print(f"\nExit list saved to: results/exit_list.csv")
