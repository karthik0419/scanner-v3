import pandas as pd
from datetime import datetime

# Load data
this_week = pd.read_csv('results/v3_2026-08-27.csv')
tracker = pd.read_csv('results/paper_tracker.csv')

print("\n" + "="*80)
print("📊 SCANNER-V3 PERFORMANCE CHECK")
print("="*80)

# This week's scan
print(f"\n🆕 THIS WEEK'S SCAN (2026-08-27):")
print(f"   Total picks: {len(this_week)}")
print(f"   BREAKOUT: {len(this_week[this_week['status']=='BREAKOUT'])}")
print(f"   NEAR: {len(this_week[this_week['status']=='NEAR'])}")
print(f"   WATCH: {len(this_week[this_week['status']=='WATCH'])}")

print(f"\n   Top sectors:")
sector_counts = this_week['sector'].value_counts().head(5)
for sector, count in sector_counts.items():
    print(f"   - {sector}: {count} picks")

# Paper tracker status
print(f"\n📈 PAPER TRACKER (Current Portfolio):")
print(f"   Total positions: {len(tracker)}")
print(f"   OPEN: {len(tracker[tracker['status']=='OPEN'])}")
print(f"   WIN_T1: {len(tracker[tracker['status']=='WIN_T1'])}")
print(f"   WIN_T2: {len(tracker[tracker['status']=='WIN_T2'])}")
print(f"   LOSS: {len(tracker[tracker['status']=='LOSS'])}")
print(f"   WAITING_BREAKOUT: {len(tracker[tracker['status']=='WAITING_BREAKOUT'])}")
print(f"   TIME_EXIT: {len(tracker[tracker['status']=='TIME_EXIT'])}")

# P&L analysis
open_trades = tracker[tracker['status'].isin(['OPEN', 'WIN_T1'])]
closed_trades = tracker[tracker['status'].isin(['WIN_T1', 'WIN_T2', 'LOSS', 'TIME_EXIT'])]

print(f"\n💰 OPEN TRADES ({len(open_trades)}):")
if len(open_trades) > 0:
    profitable = open_trades[open_trades['pnl_pct'] > 0]
    losing = open_trades[open_trades['pnl_pct'] < 0]
    
    print(f"   In Profit: {len(profitable)} ({len(profitable)/len(open_trades)*100:.1f}%)")
    print(f"   In Loss: {len(losing)} ({len(losing)/len(open_trades)*100:.1f}%)")
    print(f"   Total Unrealized P&L: {open_trades['pnl_pct'].sum():.2f}%")
    print(f"   Avg P&L: {open_trades['pnl_pct'].mean():.2f}%")
    
    print(f"\n   Top 10 Gainers:")
    top_gainers = open_trades.nlargest(10, 'pnl_pct')[['symbol', 'pattern', 'pnl_pct', 'days_held']]
    for _, row in top_gainers.iterrows():
        print(f"   {row['symbol']:15} {row['pattern']:20} {row['pnl_pct']:+7.2f}% ({row['days_held']} days)")
    
    print(f"\n   Top 10 Losers:")
    top_losers = open_trades.nsmallest(10, 'pnl_pct')[['symbol', 'pattern', 'pnl_pct', 'days_held']]
    for _, row in top_losers.iterrows():
        print(f"   {row['symbol']:15} {row['pattern']:20} {row['pnl_pct']:+7.2f}% ({row['days_held']} days)")

print(f"\n✅ CLOSED TRADES ({len(closed_trades)}):")
if len(closed_trades) > 0:
    winners = closed_trades[closed_trades['pnl_pct'] > 0]
    losers = closed_trades[closed_trades['pnl_pct'] < 0]
    
    print(f"   Winners: {len(winners)} ({len(winners)/len(closed_trades)*100:.1f}%)")
    print(f"   Losers: {len(losers)} ({len(losers)/len(closed_trades)*100:.1f}%)")
    print(f"   Total Realized P&L: {closed_trades['pnl_pct'].sum():.2f}%")
    print(f"   Avg P&L: {closed_trades['pnl_pct'].mean():.2f}%")
    
    if len(winners) > 0:
        print(f"   Avg Win: {winners['pnl_pct'].mean():.2f}%")
    if len(losers) > 0:
        print(f"   Avg Loss: {losers['pnl_pct'].mean():.2f}%")

# Entries triggered this week
print(f"\n🎯 ENTRIES TRIGGERED THIS WEEK:")
recent_entries = tracker[tracker['days_held'] <= 7]
recent_entries = recent_entries[recent_entries['status'].isin(['OPEN', 'WIN_T1', 'LOSS'])]
print(f"   Total: {len(recent_entries)}")

if len(recent_entries) > 0:
    print(f"\n   Recent entries:")
    for _, row in recent_entries.iterrows():
        print(f"   {row['symbol']:15} {row['pattern']:20} {row['status']:10} {row['pnl_pct']:+7.2f}% ({row['days_held']} days)")

# Summary
print(f"\n📊 OVERALL SUMMARY:")
all_trades = tracker[tracker['status'] != 'WATCH']
total_pnl = all_trades['pnl_pct'].sum()
avg_pnl = all_trades['pnl_pct'].mean()

print(f"   Total Trades: {len(all_trades)}")
print(f"   Total P&L: {total_pnl:+.2f}%")
print(f"   Avg P&L per trade: {avg_pnl:+.2f}%")

print("\n" + "="*80)
