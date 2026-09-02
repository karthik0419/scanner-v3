"""
Analyze SwingIQ BREAKOUT picks from August 17-27, 2026
Check actual performance with proper price fetching
"""

import pandas as pd
import yfinance as yf
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("\n" + "="*100)
print("📊 SWINGIQ BREAKOUT PERFORMANCE: AUGUST 17-27, 2026")
print("="*100)

# Load all scans from Aug 17-27
dates = ['2026-08-17', '2026-08-18', '2026-08-19', '2026-08-20', '2026-08-21', 
         '2026-08-22', '2026-08-23', '2026-08-24', '2026-08-25', '2026-08-26', '2026-08-27']

all_picks = []

for date in dates:
    try:
        df = pd.read_csv(f'results/v3_{date}.csv')
        df['scan_date'] = date
        all_picks.append(df)
    except:
        pass

all_df = pd.concat(all_picks, ignore_index=True)

print(f"\n📅 Loaded {len(dates)} days of scans")
print(f"   Total picks: {len(all_df)}")
print(f"   Unique stocks: {all_df['symbol'].nunique()}")

# Get BREAKOUT picks only
breakout_picks = all_df[all_df['status'] == 'BREAKOUT'].copy()
print(f"\n🎯 BREAKOUT picks (ready to enter): {len(breakout_picks)}")
print(f"   Unique stocks: {breakout_picks['symbol'].nunique()}")

# Get unique symbols and their first appearance
first_breakout = breakout_picks.sort_values('scan_date').drop_duplicates('symbol', keep='first')
print(f"\n   First-time BREAKOUT: {len(first_breakout)} stocks")

# Fetch current prices
print(f"\n📥 Fetching current prices...")

results = []

for _, row in first_breakout.iterrows():
    symbol = row['symbol']
    scan_date = row['scan_date']
    entry = row['breakout']
    stop_loss = row['stop_loss']
    target1 = row['target_1']
    target2 = row['target_2']
    pattern = row['pattern']
    sector = row['sector']
    score = row['score']
    
    try:
        # Fetch price data from scan date to now
        ticker = yf.Ticker(symbol)
        start_date = datetime.strptime(scan_date, '%Y-%m-%d')
        hist = ticker.history(start=start_date, end=datetime.now())
        
        if hist.empty:
            continue
        
        # Get current price (latest close)
        current = float(hist['Close'].iloc[-1])
        
        # Calculate P&L from entry (breakout level)
        pnl_pct = ((current - entry) / entry) * 100
        
        # Determine status
        if current >= target2:
            status = '✅✅ WIN_T2'
        elif current >= target1:
            status = '✅ WIN_T1'
        elif current <= stop_loss:
            status = '❌ LOSS'
        else:
            if pnl_pct > 0:
                status = '📈 OPEN (Profit)'
            else:
                status = '📉 OPEN (Loss)'
        
        # Days held
        days_held = (datetime.now() - start_date).days
        
        results.append({
            'symbol': symbol,
            'scan_date': scan_date,
            'pattern': pattern,
            'sector': sector,
            'score': score,
            'entry': entry,
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'current': current,
            'pnl_pct': pnl_pct,
            'status': status,
            'days_held': days_held
        })
        
        print(f"   ✓ {symbol}: {pnl_pct:+.2f}%")
        
    except Exception as e:
        print(f"   ✗ {symbol}: Failed ({str(e)[:50]})")
        continue

if not results:
    print("\n❌ No results to analyze!")
    exit()

results_df = pd.DataFrame(results)
results_df = results_df.sort_values('pnl_pct', ascending=False)

# Overall stats
print("\n" + "="*100)
print("📊 OVERALL PERFORMANCE")
print("="*100)

total = len(results_df)
winners = len(results_df[results_df['pnl_pct'] > 0])
losers = len(results_df[results_df['pnl_pct'] < 0])
win_rate = (winners / total) * 100 if total > 0 else 0

print(f"\n💰 Total BREAKOUT picks analyzed: {total}")
print(f"   Winners: {winners} ({win_rate:.1f}%)")
print(f"   Losers: {losers} ({100-win_rate:.1f}%)")

if winners > 0:
    avg_win = results_df[results_df['pnl_pct'] > 0]['pnl_pct'].mean()
    print(f"\n   Avg Win: {avg_win:+.2f}%")

if losers > 0:
    avg_loss = results_df[results_df['pnl_pct'] < 0]['pnl_pct'].mean()
    print(f"   Avg Loss: {avg_loss:+.2f}%")

avg_pnl = results_df['pnl_pct'].mean()
total_pnl = results_df['pnl_pct'].sum()

print(f"\n   Avg P&L per trade: {avg_pnl:+.2f}%")
print(f"   Total P&L: {total_pnl:+.2f}%")

# Status breakdown
print(f"\n📋 STATUS BREAKDOWN:")
for status in results_df['status'].unique():
    count = len(results_df[results_df['status'] == status])
    pct = (count / total) * 100
    avg = results_df[results_df['status'] == status]['pnl_pct'].mean()
    print(f"   {status}: {count} ({pct:.1f}%), Avg: {avg:+.2f}%")

# Top 10 winners
print(f"\n" + "="*100)
print("🏆 TOP 10 WINNERS")
print("="*100)

top10 = results_df.nlargest(10, 'pnl_pct')
print(f"\n{'Symbol':<15} {'Date':<12} {'Pattern':<20} {'Sector':<15} {'Entry':<10} {'Current':<10} {'P&L%':<10} {'Days':<5}")
print("-"*100)

for _, row in top10.iterrows():
    print(f"{row['symbol']:<15} {row['scan_date']:<12} {row['pattern']:<20} {row['sector']:<15} "
          f"{row['entry']:<10.2f} {row['current']:<10.2f} {row['pnl_pct']:+9.2f}% {row['days_held']:<5}")

# Top 10 losers
print(f"\n" + "="*100)
print("💔 TOP 10 LOSERS")
print("="*100)

bottom10 = results_df.nsmallest(10, 'pnl_pct')
print(f"\n{'Symbol':<15} {'Date':<12} {'Pattern':<20} {'Sector':<15} {'Entry':<10} {'Current':<10} {'P&L%':<10} {'Days':<5}")
print("-"*100)

for _, row in bottom10.iterrows():
    print(f"{row['symbol']:<15} {row['scan_date']:<12} {row['pattern']:<20} {row['sector']:<15} "
          f"{row['entry']:<10.2f} {row['current']:<10.2f} {row['pnl_pct']:+9.2f}% {row['days_held']:<5}")

# By date
print(f"\n" + "="*100)
print("📅 PERFORMANCE BY DATE")
print("="*100)

for date in sorted(results_df['scan_date'].unique()):
    date_df = results_df[results_df['scan_date'] == date]
    date_winners = len(date_df[date_df['pnl_pct'] > 0])
    date_wr = (date_winners / len(date_df)) * 100
    date_avg = date_df['pnl_pct'].mean()
    
    print(f"\n{date}: {len(date_df)} picks, {date_wr:.1f}% WR, {date_avg:+.2f}% avg")
    
    for _, row in date_df.iterrows():
        print(f"  {row['symbol']:15} {row['pattern']:20} {row['pnl_pct']:+7.2f}% ({row['status']})")

# By sector
print(f"\n" + "="*100)
print("📊 PERFORMANCE BY SECTOR")
print("="*100)

sector_stats = results_df.groupby('sector').agg({
    'pnl_pct': ['count', 'mean', 'sum']
}).round(2)

sector_stats.columns = ['Count', 'Avg P&L%', 'Total P&L%']
sector_stats = sector_stats.sort_values('Avg P&L%', ascending=False)

print(f"\n{sector_stats}")

# Save results
results_df.to_csv('results/aug17_27_performance.csv', index=False)
print(f"\n" + "="*100)
print(f"💾 Results saved to: results/aug17_27_performance.csv")
print("="*100 + "\n")
