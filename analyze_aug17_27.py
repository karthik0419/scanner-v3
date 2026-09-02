"""
Analyze SwingIQ picks from August 17-27, 2026
Check which ones triggered and their current performance
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

print("\n" + "="*100)
print("SWINGIQ PERFORMANCE ANALYSIS: AUGUST 17-27, 2026")
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
        print(f"Loaded {date}: {len(df)} picks")
    except:
        print(f"Skipped {date}: File not found")

if not all_picks:
    print("\nNo scan files found!")
    exit()

# Combine all picks
all_df = pd.concat(all_picks, ignore_index=True)

print(f"\nTotal picks across all dates: {len(all_df)}")
print(f"Unique stocks: {all_df['symbol'].nunique()}")

# Get BREAKOUT picks (ready to enter)
breakout_picks = all_df[all_df['status'] == 'BREAKOUT'].copy()
print(f"\nBREAKOUT picks (ready to enter): {len(breakout_picks)}")

# Get current prices for all unique symbols
unique_symbols = breakout_picks['symbol'].unique()
print(f"\nFetching current prices for {len(unique_symbols)} stocks...")

current_prices = {}
for symbol in unique_symbols:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='5d')
        if not hist.empty:
            current_prices[symbol] = hist['Close'].iloc[-1]
    except:
        pass

print(f"Got prices for {len(current_prices)} stocks")

# Calculate performance
results = []

for _, row in breakout_picks.iterrows():
    symbol = row['symbol']
    scan_date = row['scan_date']
    entry = row['breakout']
    stop_loss = row['stop_loss']
    target1 = row['target_1']
    target2 = row['target_2']
    pattern = row['pattern']
    sector = row['sector']
    score = row['score']
    
    if symbol not in current_prices:
        continue
    
    current = current_prices[symbol]
    
    # Calculate P&L
    pnl_pct = ((current - entry) / entry) * 100
    
    # Determine status
    if current >= target2:
        status = 'WIN_T2'
    elif current >= target1:
        status = 'WIN_T1'
    elif current <= stop_loss:
        status = 'LOSS'
    else:
        status = 'OPEN'
    
    # Days held
    scan_dt = datetime.strptime(scan_date, '%Y-%m-%d')
    days_held = (datetime.now() - scan_dt).days
    
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

if not results:
    print("\nNo results to analyze!")
    exit()

results_df = pd.DataFrame(results)

# Sort by P&L
results_df = results_df.sort_values('pnl_pct', ascending=False)

# Overall stats
print("\n" + "="*100)
print("OVERALL PERFORMANCE")
print("="*100)

total = len(results_df)
winners = len(results_df[results_df['pnl_pct'] > 0])
losers = len(results_df[results_df['pnl_pct'] < 0])
win_rate = (winners / total) * 100

print(f"\nTotal BREAKOUT picks: {total}")
print(f"Winners: {winners} ({win_rate:.1f}%)")
print(f"Losers: {losers} ({100-win_rate:.1f}%)")

avg_win = results_df[results_df['pnl_pct'] > 0]['pnl_pct'].mean() if winners > 0 else 0
avg_loss = results_df[results_df['pnl_pct'] < 0]['pnl_pct'].mean() if losers > 0 else 0

print(f"\nAvg Win: {avg_win:+.2f}%")
print(f"Avg Loss: {avg_loss:+.2f}%")
print(f"Avg P&L: {results_df['pnl_pct'].mean():+.2f}%")

# Status breakdown
print(f"\nSTATUS BREAKDOWN:")
status_counts = results_df['status'].value_counts()
for status, count in status_counts.items():
    pct = (count / total) * 100
    avg_pnl = results_df[results_df['status'] == status]['pnl_pct'].mean()
    print(f"  {status}: {count} ({pct:.1f}%), Avg P&L: {avg_pnl:+.2f}%")

# By date
print(f"\n" + "="*100)
print("PERFORMANCE BY DATE")
print("="*100)

for date in sorted(results_df['scan_date'].unique()):
    date_df = results_df[results_df['scan_date'] == date]
    date_winners = len(date_df[date_df['pnl_pct'] > 0])
    date_wr = (date_winners / len(date_df)) * 100
    date_avg = date_df['pnl_pct'].mean()
    
    print(f"\n{date}: {len(date_df)} picks, {date_wr:.1f}% WR, {date_avg:+.2f}% avg P&L")
    
    # Top 3 from this date
    top3 = date_df.nlargest(3, 'pnl_pct')
    for _, row in top3.iterrows():
        print(f"  {row['symbol']:15} {row['pattern']:20} {row['pnl_pct']:+7.2f}% ({row['status']})")

# Top 20 winners
print(f"\n" + "="*100)
print("TOP 20 WINNERS")
print("="*100)

top20 = results_df.nlargest(20, 'pnl_pct')
print(f"\n{'Symbol':<15} {'Date':<12} {'Pattern':<20} {'Sector':<15} {'Entry':<10} {'Current':<10} {'P&L%':<10} {'Status':<10}")
print("-"*100)

for _, row in top20.iterrows():
    print(f"{row['symbol']:<15} {row['scan_date']:<12} {row['pattern']:<20} {row['sector']:<15} "
          f"{row['entry']:<10.2f} {row['current']:<10.2f} {row['pnl_pct']:+9.2f}% {row['status']:<10}")

# Top 20 losers
print(f"\n" + "="*100)
print("TOP 20 LOSERS")
print("="*100)

bottom20 = results_df.nsmallest(20, 'pnl_pct')
print(f"\n{'Symbol':<15} {'Date':<12} {'Pattern':<20} {'Sector':<15} {'Entry':<10} {'Current':<10} {'P&L%':<10} {'Status':<10}")
print("-"*100)

for _, row in bottom20.iterrows():
    print(f"{row['symbol']:<15} {row['scan_date']:<12} {row['pattern']:<20} {row['sector']:<15} "
          f"{row['entry']:<10.2f} {row['current']:<10.2f} {row['pnl_pct']:+9.2f}% {row['status']:<10}")

# By sector
print(f"\n" + "="*100)
print("PERFORMANCE BY SECTOR")
print("="*100)

sector_stats = results_df.groupby('sector').agg({
    'pnl_pct': ['count', 'mean', 'sum'],
    'symbol': 'count'
}).round(2)

sector_stats.columns = ['Count', 'Avg P&L%', 'Total P&L%', 'Stocks']
sector_stats = sector_stats.sort_values('Avg P&L%', ascending=False)

print(sector_stats)

# By pattern
print(f"\n" + "="*100)
print("PERFORMANCE BY PATTERN")
print("="*100)

pattern_stats = results_df.groupby('pattern').agg({
    'pnl_pct': ['count', 'mean', 'sum'],
    'symbol': 'count'
}).round(2)

pattern_stats.columns = ['Count', 'Avg P&L%', 'Total P&L%', 'Stocks']
pattern_stats = pattern_stats.sort_values('Avg P&L%', ascending=False)

print(pattern_stats)

# Save results
results_df.to_csv('results/aug17_27_performance.csv', index=False)
print(f"\n" + "="*100)
print(f"Results saved to: results/aug17_27_performance.csv")
print("="*100 + "\n")
