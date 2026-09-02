"""Exit weak sector trades from paper tracker"""
import pandas as pd
from datetime import date

# Load tracker
tracker = pd.read_csv('results/paper_tracker.csv')

# Load exit list
exit_list = pd.read_csv('results/exit_list.csv')
exit_symbols = set(exit_list['symbol'].tolist())

print("=" * 80)
print("EXITING WEAK SECTOR TRADES")
print("=" * 80)
print(f"\nTotal trades to exit: {len(exit_symbols)}")
print(f"Total loss: {exit_list['pnl'].sum():.2f}%")
print()

# Update tracker - mark as LOSS (manual exit)
exited_count = 0
for idx, row in tracker.iterrows():
    if row['symbol'] in exit_symbols and row['current_status'] == 'OPEN':
        # Mark as LOSS (manual exit)
        tracker.at[idx, 'current_status'] = 'LOSS'
        tracker.at[idx, 'exit_date'] = str(date.today())
        tracker.at[idx, 'exit_price'] = row['current_price']
        tracker.at[idx, 'exit_reason'] = 'Manual Exit - Weak Sector'
        
        sector = exit_list[exit_list['symbol']==row['symbol']]['sector'].iloc[0]
        print(f"[EXIT] {row['symbol']:<20} ({sector:<15}) P&L: {row['current_pnl_pct']:>6.2f}%")
        exited_count += 1

# Save updated tracker
tracker.to_csv('results/paper_tracker.csv', index=False)

print("\n" + "=" * 80)
print(f"Successfully exited {exited_count} trades")
print(f"Tracker updated: results/paper_tracker.csv")
print("=" * 80)

# Show updated summary
open_trades = tracker[tracker['current_status'] == 'OPEN']
closed_trades = tracker[tracker['current_status'].isin(['LOSS', 'WIN_T2', 'TIME_EXIT'])]

print("\n" + "=" * 80)
print("UPDATED PORTFOLIO STATUS")
print("=" * 80)
print(f"Open trades: {len(open_trades)}")
print(f"Closed trades: {len(closed_trades)}")
print(f"Open avg P&L: {open_trades['current_pnl_pct'].mean():.2f}%")
print(f"Closed avg P&L: {closed_trades['current_pnl_pct'].mean():.2f}%")
print("=" * 80)

print("\nNext steps:")
print("  1. Run: python paper_tracker.py status")
print("  2. Check remaining open trades")
print("  3. Use --defensive flag for new scans")
print("  4. Focus on HOT sectors only (Pharma, IT, FMCG)")
