"""Manually exit a stock from paper tracker"""
import sys
import pandas as pd
from datetime import date

if len(sys.argv) < 2:
    print("Usage: python manual_exit.py <SYMBOL> [exit_price]")
    print("Example: python manual_exit.py VEEDOL.NS 1475")
    sys.exit(1)

symbol = sys.argv[1]
if not symbol.endswith('.NS'):
    symbol = symbol + '.NS'

# Load tracker
df = pd.read_csv('results/paper_tracker.csv')

# Find stock
stock = df[df['symbol'] == symbol]

if len(stock) == 0:
    print(f"{symbol} not found in tracker")
    sys.exit(1)

idx = stock.index[0]
row = stock.iloc[0]

# Get exit price (from command line or use current price)
if len(sys.argv) >= 3:
    exit_price = float(sys.argv[2])
else:
    exit_price = row['current_price']

# Calculate P&L
exit_pnl = ((exit_price - row['entry_price']) / row['entry_price']) * 100

print("=" * 80)
print(f"MANUAL EXIT - {symbol}")
print("=" * 80)
print(f"Entry Price:   Rs {row['entry_price']:.2f}")
print(f"Exit Price:    Rs {exit_price:.2f}")
print(f"P&L:           {exit_pnl:.2f}%")
print(f"Days Held:     {row['days_held']}")
print(f"Pattern:       {row['pattern']}")
print("=" * 80)

# Confirm
confirm = input("\nConfirm exit? (y/n): ")
if confirm.lower() != 'y':
    print("Exit cancelled")
    sys.exit(0)

# Update tracker
df.at[idx, 'current_status'] = 'LOSS'
df.at[idx, 'exit_date'] = str(date.today())
df.at[idx, 'exit_price'] = exit_price
df.at[idx, 'current_price'] = exit_price
df.at[idx, 'current_pnl_pct'] = exit_pnl
df.at[idx, 'exit_reason'] = 'Manual Exit - User Decision'

# Save
df.to_csv('results/paper_tracker.csv', index=False)

print("\n" + "=" * 80)
print(f"SUCCESS - {symbol} exited")
print("=" * 80)
print(f"Exit Price: Rs {exit_price:.2f}")
print(f"P&L: {exit_pnl:.2f}%")
print(f"Tracker updated: results/paper_tracker.csv")
print("=" * 80)

# Show updated summary
open_trades = df[df['current_status'] == 'OPEN']
closed_trades = df[df['current_status'].isin(['LOSS', 'WIN_T2', 'TIME_EXIT'])]

print("\nUPDATED PORTFOLIO:")
print(f"Open: {len(open_trades)} | Closed: {len(closed_trades)}")
print(f"Open avg P&L: {open_trades['current_pnl_pct'].mean():.2f}%")
