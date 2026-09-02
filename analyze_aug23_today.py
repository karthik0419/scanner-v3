"""
Detailed Analysis: August 23 - August 28, 2026
Track all BREAKOUT picks and their performance
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

print("\n" + "="*100)
print("📊 SWINGIQ DETAILED REPORT: AUGUST 23-28, 2026")
print("="*100)

# Load scans from Aug 23-28
dates = ['2026-08-23', '2026-08-24', '2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28']

all_picks = []
scan_summary = []

for date in dates:
    try:
        df = pd.read_csv(f'results/v3_{date}.csv')
        df['scan_date'] = date
        all_picks.append(df)
        
        breakout_count = len(df[df['status'] == 'BREAKOUT'])
        near_count = len(df[df['status'] == 'NEAR'])
        watch_count = len(df[df['status'] == 'WATCH'])
        
        scan_summary.append({
            'date': date,
            'total': len(df),
            'breakout': breakout_count,
            'near': near_count,
            'watch': watch_count
        })
        
        print(f"✓ {date}: {len(df)} picks ({breakout_count} BREAKOUT, {near_count} NEAR, {watch_count} WATCH)")
    except:
        print(f"✗ {date}: File not found")

if not all_picks:
    print("\n❌ No scan files found!")
    exit()

# Combine all picks
all_df = pd.concat(all_picks, ignore_index=True)

print(f"\n📊 SUMMARY:")
print(f"   Total picks: {len(all_df)}")
print(f"   Unique stocks: {all_df['symbol'].nunique()}")
print(f"   Date range: {len(dates)} days")

# Get BREAKOUT picks only
breakout_picks = all_df[all_df['status'] == 'BREAKOUT'].copy()
print(f"\n🎯 BREAKOUT PICKS:")
print(f"   Total: {len(breakout_picks)}")
print(f"   Unique stocks: {breakout_picks['symbol'].nunique()}")

# Get first appearance of each stock
first_breakout = breakout_picks.sort_values('scan_date').drop_duplicates('symbol', keep='first')
print(f"   First-time BREAKOUT: {len(first_breakout)} stocks")

# Fetch current prices and calculate performance
print(f"\n📥 FETCHING CURRENT PRICES...")

results = []
failed = []

for idx, row in first_breakout.iterrows():
    symbol = row['symbol']
    scan_date = row['scan_date']
    entry = row['breakout']
    stop_loss = row['stop_loss']
    target1 = row['target_1']
    target2 = row['target_2']
    pattern = row['pattern']
    sector = row['sector']
    score = row['score']
    timeframe = row.get('timeframe', 'Daily')
    
    try:
        # Fetch price data
        ticker = yf.Ticker(symbol)
        start_date = datetime.strptime(scan_date, '%Y-%m-%d')
        hist = ticker.history(start=start_date, end=datetime.now() + timedelta(days=1))
        
        if hist.empty:
            failed.append({'symbol': symbol, 'reason': 'No data'})
            continue
        
        # Get entry price (close on scan date or next available)
        if len(hist) > 0:
            entry_price = float(hist['Close'].iloc[0])
        else:
            failed.append({'symbol': symbol, 'reason': 'No entry price'})
            continue
        
        # Get current price (latest close)
        current = float(hist['Close'].iloc[-1])
        
        # Get high and low during holding period
        high = float(hist['High'].max())
        low = float(hist['Low'].min())
        
        # Calculate P&L from entry
        pnl_pct = ((current - entry_price) / entry_price) * 100
        
        # Check if hit targets or stop loss
        hit_t1 = high >= target1
        hit_t2 = high >= target2
        hit_sl = low <= stop_loss
        
        # Determine status
        if hit_t2:
            status = '✅✅ WIN_T2'
            exit_price = target2
            exit_pnl = ((target2 - entry_price) / entry_price) * 100
        elif hit_t1:
            status = '✅ WIN_T1'
            exit_price = target1
            exit_pnl = ((target1 - entry_price) / entry_price) * 100
        elif hit_sl:
            status = '❌ LOSS'
            exit_price = stop_loss
            exit_pnl = ((stop_loss - entry_price) / entry_price) * 100
        else:
            if pnl_pct > 0:
                status = '📈 OPEN (Profit)'
            else:
                status = '📉 OPEN (Loss)'
            exit_price = current
            exit_pnl = pnl_pct
        
        # Days held
        days_held = (datetime.now() - start_date).days
        
        results.append({
            'symbol': symbol,
            'scan_date': scan_date,
            'pattern': pattern,
            'timeframe': timeframe,
            'sector': sector,
            'score': score,
            'entry': entry_price,
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'current': current,
            'high': high,
            'low': low,
            'pnl_pct': pnl_pct,
            'exit_pnl': exit_pnl,
            'status': status,
            'hit_t1': hit_t1,
            'hit_t2': hit_t2,
            'hit_sl': hit_sl,
            'days_held': days_held
        })
        
        print(f"   ✓ {symbol:15} {scan_date} → {status:20} {exit_pnl:+7.2f}%")
        
    except Exception as e:
        failed.append({'symbol': symbol, 'reason': str(e)[:50]})
        print(f"   ✗ {symbol:15} Failed: {str(e)[:50]}")

print(f"\n✅ Successfully analyzed: {len(results)} stocks")
print(f"❌ Failed to analyze: {len(failed)} stocks")

if not results:
    print("\n❌ No results to analyze!")
    exit()

results_df = pd.DataFrame(results)
results_df = results_df.sort_values('exit_pnl', ascending=False)

# OVERALL STATISTICS
print("\n" + "="*100)
print("📊 OVERALL PERFORMANCE")
print("="*100)

total = len(results_df)
closed = len(results_df[results_df['status'].str.contains('WIN|LOSS')])
open_trades = len(results_df[results_df['status'].str.contains('OPEN')])

win_t2 = len(results_df[results_df['status'] == '✅✅ WIN_T2'])
win_t1 = len(results_df[results_df['status'] == '✅ WIN_T1'])
losses = len(results_df[results_df['status'] == '❌ LOSS'])
open_profit = len(results_df[results_df['status'] == '📈 OPEN (Profit)'])
open_loss = len(results_df[results_df['status'] == '📉 OPEN (Loss)'])

winners = win_t1 + win_t2
win_rate = (winners / closed * 100) if closed > 0 else 0

print(f"\n💼 PORTFOLIO STATUS:")
print(f"   Total Trades: {total}")
print(f"   Closed: {closed} ({closed/total*100:.1f}%)")
print(f"   Open: {open_trades} ({open_trades/total*100:.1f}%)")

print(f"\n🎯 CLOSED TRADES ({closed}):")
print(f"   WIN_T2: {win_t2} ({win_t2/closed*100:.1f}%)" if closed > 0 else "   WIN_T2: 0")
print(f"   WIN_T1: {win_t1} ({win_t1/closed*100:.1f}%)" if closed > 0 else "   WIN_T1: 0")
print(f"   LOSS: {losses} ({losses/closed*100:.1f}%)" if closed > 0 else "   LOSS: 0")
print(f"   Win Rate: {win_rate:.1f}%")

print(f"\n📊 OPEN TRADES ({open_trades}):")
print(f"   In Profit: {open_profit} ({open_profit/open_trades*100:.1f}%)" if open_trades > 0 else "   In Profit: 0")
print(f"   In Loss: {open_loss} ({open_loss/open_trades*100:.1f}%)" if open_trades > 0 else "   In Loss: 0")

# P&L Analysis
closed_df = results_df[results_df['status'].str.contains('WIN|LOSS')]
if len(closed_df) > 0:
    avg_pnl = closed_df['exit_pnl'].mean()
    total_pnl = closed_df['exit_pnl'].sum()
    
    winners_df = closed_df[closed_df['status'].str.contains('WIN')]
    losers_df = closed_df[closed_df['status'] == '❌ LOSS']
    
    if len(winners_df) > 0:
        avg_win = winners_df['exit_pnl'].mean()
        print(f"\n💰 CLOSED TRADES P&L:")
        print(f"   Avg Win: {avg_win:+.2f}%")
    
    if len(losers_df) > 0:
        avg_loss = losers_df['exit_pnl'].mean()
        print(f"   Avg Loss: {avg_loss:+.2f}%")
    
    print(f"   Avg P&L: {avg_pnl:+.2f}%")
    print(f"   Total P&L: {total_pnl:+.2f}%")

# Open trades P&L
open_df = results_df[results_df['status'].str.contains('OPEN')]
if len(open_df) > 0:
    open_avg = open_df['pnl_pct'].mean()
    open_total = open_df['pnl_pct'].sum()
    
    print(f"\n📈 OPEN TRADES P&L:")
    print(f"   Avg P&L: {open_avg:+.2f}%")
    print(f"   Total Unrealized: {open_total:+.2f}%")

# DAILY BREAKDOWN
print(f"\n" + "="*100)
print("📅 PERFORMANCE BY DATE")
print("="*100)

for date in sorted(results_df['scan_date'].unique()):
    date_df = results_df[results_df['scan_date'] == date]
    date_closed = date_df[date_df['status'].str.contains('WIN|LOSS')]
    date_open = date_df[date_df['status'].str.contains('OPEN')]
    
    if len(date_closed) > 0:
        date_winners = len(date_closed[date_closed['status'].str.contains('WIN')])
        date_wr = (date_winners / len(date_closed)) * 100
        date_avg = date_closed['exit_pnl'].mean()
    else:
        date_wr = 0
        date_avg = 0
    
    print(f"\n📆 {date}: {len(date_df)} picks")
    print(f"   Closed: {len(date_closed)} ({date_wr:.1f}% WR, {date_avg:+.2f}% avg)")
    print(f"   Open: {len(date_open)}")
    
    print(f"\n   {'Symbol':<15} {'Pattern':<20} {'Sector':<15} {'Entry':<10} {'Current':<10} {'P&L%':<10} {'Status':<20}")
    print("   " + "-"*95)
    
    for _, row in date_df.iterrows():
        print(f"   {row['symbol']:<15} {row['pattern']:<20} {row['sector']:<15} "
              f"{row['entry']:<10.2f} {row['current']:<10.2f} {row['exit_pnl']:+9.2f}% {row['status']:<20}")

# TOP PERFORMERS
print(f"\n" + "="*100)
print("🏆 TOP 10 BEST TRADES")
print("="*100)

top10 = results_df.nlargest(10, 'exit_pnl')
print(f"\n{'Symbol':<15} {'Date':<12} {'Pattern':<20} {'Sector':<15} {'Entry':<10} {'Current':<10} {'P&L%':<10} {'Days':<5} {'Status':<20}")
print("-"*110)

for _, row in top10.iterrows():
    print(f"{row['symbol']:<15} {row['scan_date']:<12} {row['pattern']:<20} {row['sector']:<15} "
          f"{row['entry']:<10.2f} {row['current']:<10.2f} {row['exit_pnl']:+9.2f}% {row['days_held']:<5} {row['status']:<20}")

# WORST PERFORMERS
print(f"\n" + "="*100)
print("💔 TOP 10 WORST TRADES")
print("="*100)

bottom10 = results_df.nsmallest(10, 'exit_pnl')
print(f"\n{'Symbol':<15} {'Date':<12} {'Pattern':<20} {'Sector':<15} {'Entry':<10} {'Current':<10} {'P&L%':<10} {'Days':<5} {'Status':<20}")
print("-"*110)

for _, row in bottom10.iterrows():
    print(f"{row['symbol']:<15} {row['scan_date']:<12} {row['pattern']:<20} {row['sector']:<15} "
          f"{row['entry']:<10.2f} {row['current']:<10.2f} {row['exit_pnl']:+9.2f}% {row['days_held']:<5} {row['status']:<20}")

# SECTOR ANALYSIS
print(f"\n" + "="*100)
print("📊 PERFORMANCE BY SECTOR")
print("="*100)

sector_stats = results_df.groupby('sector').agg({
    'exit_pnl': ['count', 'mean', 'sum'],
    'symbol': 'count'
}).round(2)

sector_stats.columns = ['Count', 'Avg P&L%', 'Total P&L%', 'Stocks']
sector_stats = sector_stats.sort_values('Avg P&L%', ascending=False)

print(f"\n{sector_stats}")

# PATTERN ANALYSIS
print(f"\n" + "="*100)
print("📊 PERFORMANCE BY PATTERN")
print("="*100)

pattern_stats = results_df.groupby('pattern').agg({
    'exit_pnl': ['count', 'mean', 'sum'],
    'symbol': 'count'
}).round(2)

pattern_stats.columns = ['Count', 'Avg P&L%', 'Total P&L%', 'Stocks']
pattern_stats = pattern_stats.sort_values('Avg P&L%', ascending=False)

print(f"\n{pattern_stats}")

# CAPITAL SIMULATION
print(f"\n" + "="*100)
print("💰 CAPITAL SIMULATION (₹50,000 starting capital)")
print("="*100)

capital = 50000
per_trade = capital / len(results_df)

print(f"\nStarting Capital: ₹{capital:,.0f}")
print(f"Trades: {len(results_df)}")
print(f"Per Trade: ₹{per_trade:,.0f}")

total_profit = 0
for _, row in results_df.iterrows():
    trade_pnl = per_trade * (row['exit_pnl'] / 100)
    total_profit += trade_pnl

final_capital = capital + total_profit
return_pct = (total_profit / capital) * 100

print(f"\nTotal P&L: ₹{total_profit:+,.0f}")
print(f"Final Capital: ₹{final_capital:,.0f}")
print(f"Return: {return_pct:+.2f}%")

days = (datetime.now() - datetime.strptime(results_df['scan_date'].min(), '%Y-%m-%d')).days
if days > 0:
    daily_return = return_pct / days
    monthly_return = daily_return * 30
    annual_return = daily_return * 365
    
    print(f"\nDaily Return: {daily_return:+.2f}%")
    print(f"Monthly Return (projected): {monthly_return:+.2f}%")
    print(f"Annual Return (projected): {annual_return:+.2f}%")

# Save results
results_df.to_csv('results/aug23_28_detailed_report.csv', index=False)

print(f"\n" + "="*100)
print(f"💾 DETAILED REPORT SAVED: results/aug23_28_detailed_report.csv")
print("="*100 + "\n")
