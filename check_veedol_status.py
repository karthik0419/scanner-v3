import pandas as pd

df = pd.read_csv('results/paper_tracker.csv')
veedol = df[df['symbol'] == 'VEEDOL.NS']

if len(veedol) > 0:
    row = veedol.iloc[0]
    print("=" * 60)
    print("VEEDOL.NS - CURRENT STATUS IN TRACKER")
    print("=" * 60)
    print(f"Status:      {row['current_status']}")
    print(f"P&L:         {row['current_pnl_pct']:.2f}%")
    print(f"Entry:       Rs {row['entry_price']:.2f}")
    print(f"Current:     Rs {row['current_price']:.2f}")
    print(f"Exit Date:   {row.get('exit_date', 'N/A')}")
    print(f"Exit Reason: {row.get('exit_reason', 'N/A')}")
    print("=" * 60)
    
    if row['current_status'] == 'LOSS':
        print("\nVEEDOL is already marked as LOSS (exited)")
        print("This was done in today's batch exit of 25 weak sector trades")
    else:
        print("\nVEEDOL is still OPEN - needs manual exit")
else:
    print("VEEDOL.NS not found in tracker")
