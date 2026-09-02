"""
BACKTEST: Scanner-v3's ACTUAL Pattern Detection (5 Years)

This uses Scanner-v3's REAL pattern detection code:
- patterns/cup_handle.py (Daily, Weekly, Monthly)
- patterns/double_bottom.py
- patterns/wedge.py
- patterns/breakout.py
- All the REAL filters, scoring, and logic

Compare to my "garbage" simplified backtest to see if it was really garbage.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import Scanner-v3's REAL pattern detectors
from patterns.cup_handle import detect_cup_handle, detect_cup_handle_weekly
from patterns.cup_handle_monthly import detect_cup_handle_monthly, resample_monthly
from patterns.double_bottom import detect_double_bottom
from patterns.wedge import detect_descending_wedge
from patterns.breakout import detect_breakout
from data.loader import _resample_weekly

def calculate_atr(data, period=14):
    """Calculate Average True Range"""
    high = data['High']
    low = data['Low']
    close = data['Close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr

def scan_stock_real_scanner(symbol, start_date, end_date):
    """
    Scan a stock using Scanner-v3's REAL pattern detection
    Returns list of signals
    """
    try:
        # Download data
        buffer_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
        data = yf.download(symbol, start=buffer_start, end=end_date, progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 250:
            return []
        
        # Calculate ATR
        data['ATR'] = calculate_atr(data, period=14)
        
        # Resample to weekly and monthly
        data_weekly = _resample_weekly(data)
        data_monthly = resample_monthly(data)
        
        # Filter to backtest period
        data = data[data.index >= start_date]
        
        signals = []
        
        # Scan each day
        for i in range(250, len(data)):
            date = data.index[i]
            
            # Get data up to this point
            df_daily = data.iloc[:i+1].copy()
            df_weekly = data_weekly[data_weekly.index <= date].copy()
            df_monthly = data_monthly[data_monthly.index <= date].copy()
            
            current_price = df_daily['Close'].iloc[-1]
            atr = df_daily['ATR'].iloc[-1]
            
            # Try all pattern detectors (Scanner-v3's REAL code)
            patterns_to_try = [
                ('Cup & Handle (Daily)', detect_cup_handle, df_daily),
                ('Cup & Handle (Weekly)', detect_cup_handle_weekly, df_weekly),
                ('Cup & Handle (Monthly)', detect_cup_handle_monthly, df_monthly),
                ('Double Bottom', detect_double_bottom, df_daily),
                ('Descending Wedge', detect_descending_wedge, df_daily),
                ('Breakout', detect_breakout, df_daily),
            ]
            
            for pattern_name, detector, df_pattern in patterns_to_try:
                if df_pattern is None or len(df_pattern) < 50:
                    continue
                
                result = detector(df_pattern)
                
                if result is None:
                    continue
                
                # Extract pattern details
                breakout = result.get('breakout', 0)
                stop_loss = result.get('stop_loss', 0)
                target = result.get('target', 0)
                status = result.get('status', 'UNKNOWN')
                
                if breakout <= 0 or target <= 0:
                    continue
                
                # Scanner-v3's ATR-based stop loss (2.0x ATR, capped at 8%)
                atr_stop = current_price - (2.0 * atr)
                
                # Use tighter of structural stop or ATR stop
                stop_loss = max(stop_loss, atr_stop)
                
                # Cap at 8% max risk
                stop_pct = ((current_price - stop_loss) / current_price) * 100
                if stop_pct > 8:
                    stop_loss = current_price * 0.92
                
                # Recalculate R:R
                risk = current_price - stop_loss
                reward = target - current_price
                rr = reward / risk if risk > 0 else 0
                
                # Scanner-v3's filters
                if rr < 1.5:
                    continue
                
                if stop_pct > 10:
                    continue
                
                # Only trade NEAR or BREAKOUT (not WATCH)
                if status not in ['NEAR', 'BREAKOUT']:
                    continue
                
                # Entry next day
                if i + 1 < len(data):
                    entry_date = data.index[i + 1]
                    entry_price = data['Open'].iloc[i + 1]
                    
                    # Adjust stop/target from entry
                    stop_loss_adj = entry_price - (current_price - stop_loss)
                    target_adj = target
                    
                    signals.append({
                        'symbol': symbol,
                        'pattern': pattern_name,
                        'signal_date': date,
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'stop_loss': stop_loss_adj,
                        'target': target_adj,
                        'status': status,
                        'rr': rr,
                        'atr': atr
                    })
        
        return signals
    
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return []

def backtest_signal(symbol, entry_date, entry_price, stop_loss, target, end_date):
    """Backtest a single signal"""
    try:
        data = yf.download(symbol, start=entry_date, end=end_date, progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 2:
            return None, None, 'NO_DATA', 0
        
        data = data.iloc[1:]
        max_hold_days = 45
        
        for i, (date, row) in enumerate(data.iterrows()):
            if row['Low'] <= stop_loss:
                exit_price = stop_loss
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                return date, exit_price, 'STOP_LOSS', pnl_pct
            
            if row['High'] >= target:
                exit_price = target
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                return date, exit_price, 'TARGET', pnl_pct
            
            if i >= max_hold_days:
                exit_price = row['Close']
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                return date, exit_price, 'TIME_EXIT', pnl_pct
        
        exit_price = data['Close'].iloc[-1]
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        return data.index[-1], exit_price, 'END_OF_DATA', pnl_pct
    
    except Exception as e:
        return None, None, f'ERROR: {e}', 0

def run_backtest(stock_universe, start_date, end_date):
    """Run backtest using Scanner-v3's REAL pattern detection"""
    print("=" * 100)
    print("SCANNER-V3 REAL PATTERN DETECTION BACKTEST (5 YEARS)")
    print("=" * 100)
    print(f"Period: {start_date} to {end_date}")
    print(f"Universe: {len(stock_universe)} stocks")
    print()
    print("Using Scanner-v3's ACTUAL code:")
    print("  - patterns/cup_handle.py (Daily, Weekly, Monthly)")
    print("  - patterns/double_bottom.py")
    print("  - patterns/wedge.py")
    print("  - patterns/breakout.py")
    print("  - 2.0x ATR stop loss (capped at 8%)")
    print("  - R:R >= 1.5")
    print("  - Max risk 10%")
    print("  - NEAR/BREAKOUT status only")
    print("=" * 100)
    print()
    
    all_signals = []
    
    print("Finding signals...")
    for i, symbol in enumerate(stock_universe):
        if (i + 1) % 5 == 0:
            print(f"  Processed {i + 1}/{len(stock_universe)} stocks...")
        
        signals = scan_stock_real_scanner(symbol, start_date, end_date)
        all_signals.extend(signals)
    
    print(f"Found {len(all_signals)} signals")
    print()
    
    if len(all_signals) == 0:
        print("No signals found!")
        return None
    
    # Backtest
    print("Backtesting signals...")
    results = []
    
    for i, signal in enumerate(all_signals):
        if (i + 1) % 100 == 0:
            print(f"  Backtested {i + 1}/{len(all_signals)} signals...")
        
        exit_date, exit_price, exit_reason, pnl_pct = backtest_signal(
            signal['symbol'],
            signal['entry_date'],
            signal['entry_price'],
            signal['stop_loss'],
            signal['target'],
            end_date
        )
        
        if exit_date is not None:
            results.append({
                **signal,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'pnl_pct': pnl_pct
            })
    
    print(f"Completed {len(results)} trades")
    print()
    
    # Analyze
    df = pd.DataFrame(results)
    
    if len(df) == 0:
        print("No completed trades!")
        return None
    
    total_trades = len(df)
    winners = df[df['pnl_pct'] > 0]
    losers = df[df['pnl_pct'] < 0]
    
    win_rate = len(winners) / total_trades * 100
    avg_win = winners['pnl_pct'].mean() if len(winners) > 0 else 0
    avg_loss = losers['pnl_pct'].mean() if len(losers) > 0 else 0
    avg_pnl = df['pnl_pct'].mean()
    
    expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
    
    gross_profit = winners['pnl_pct'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    df = df.sort_values('exit_date')
    df['cumulative_pnl'] = df['pnl_pct'].cumsum()
    df['running_max'] = df['cumulative_pnl'].cummax()
    df['drawdown'] = df['cumulative_pnl'] - df['running_max']
    max_drawdown = df['drawdown'].min()
    
    # Results
    print("=" * 100)
    print("RESULTS")
    print("=" * 100)
    print(f"Total trades: {total_trades}")
    print(f"Winners: {len(winners)} ({win_rate:.1f}%)")
    print(f"Losers: {len(losers)} ({100 - win_rate:.1f}%)")
    print()
    print(f"Avg win: {avg_win:+.2f}%")
    print(f"Avg loss: {avg_loss:+.2f}%")
    print(f"Avg P&L: {avg_pnl:+.2f}%")
    print()
    print(f"Expectancy: {expectancy:+.2f}%")
    print(f"Profit factor: {profit_factor:.2f}")
    print(f"Max drawdown: {max_drawdown:.2f}%")
    print()
    
    # Pattern breakdown
    print("Pattern breakdown:")
    for pattern in df['pattern'].unique():
        pattern_df = df[df['pattern'] == pattern]
        pattern_win_rate = len(pattern_df[pattern_df['pnl_pct'] > 0]) / len(pattern_df) * 100
        pattern_avg_pnl = pattern_df['pnl_pct'].mean()
        print(f"  {pattern:30} {len(pattern_df):4} trades | Win rate: {pattern_win_rate:5.1f}% | Avg P&L: {pattern_avg_pnl:+6.2f}%")
    print()
    
    # Exit reasons
    print("Exit reasons:")
    for reason, count in df['exit_reason'].value_counts().items():
        pct = count / total_trades * 100
        avg_pnl_reason = df[df['exit_reason'] == reason]['pnl_pct'].mean()
        print(f"  {reason:15} {count:4} ({pct:5.1f}%) | Avg P&L: {avg_pnl_reason:+.2f}%")
    print()
    
    # Best/worst
    print("Best trades:")
    best = df.nlargest(5, 'pnl_pct')[['symbol', 'pattern', 'entry_date', 'pnl_pct']]
    for _, row in best.iterrows():
        print(f"  {row['symbol']:15} {row['pattern']:30} {row['entry_date'].strftime('%Y-%m-%d')} | {row['pnl_pct']:+6.2f}%")
    print()
    
    print("Worst trades:")
    worst = df.nsmallest(5, 'pnl_pct')[['symbol', 'pattern', 'entry_date', 'pnl_pct']]
    for _, row in worst.iterrows():
        print(f"  {row['symbol']:15} {row['pattern']:30} {row['entry_date'].strftime('%Y-%m-%d')} | {row['pnl_pct']:+6.2f}%")
    print()
    
    # Save
    output_file = f'results/real_scanner_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    print()
    
    return df

if __name__ == '__main__':
    print("Loading stock universe...")
    
    try:
        with open('temp/quick_test.txt', 'r') as f:
            stocks = [line.strip() + '.NS' for line in f if line.strip()]
        print(f"Loaded {len(stocks)} stocks (quick test)")
    except:
        print("ERROR: Could not load stock universe!")
        exit(1)
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
    
    results = run_backtest(stocks, start_date, end_date)
    
    if results is not None:
        print()
        print("=" * 100)
        print("COMPARISON: REAL SCANNER vs MY GARBAGE BACKTEST")
        print("=" * 100)
        print()
        
        print("Scanner-v3 PROVEN (from AGENTS.md):")
        print("  Trades: 3012")
        print("  Win rate: 40.6%")
        print("  Avg win: +7.6%")
        print("  Avg loss: -3.0%")
        print("  Expectancy: +1.30%")
        print("  Profit factor: 1.73")
        print("  Max drawdown: -60.1%")
        print()
        
        print("My 'Garbage' Combined Backtest:")
        print("  Trades: 1828")
        print("  Win rate: 24.5%")
        print("  Avg win: +10.20%")
        print("  Avg loss: -3.12%")
        print("  Expectancy: +0.15%")
        print("  Profit factor: 1.06")
        print("  Max drawdown: -823.55%")
        print()
        
        print("REAL Scanner-v3 Code (this test):")
        winners = results[results['pnl_pct'] > 0]
        losers = results[results['pnl_pct'] < 0]
        win_rate = len(winners) / len(results) * 100
        avg_win = winners['pnl_pct'].mean()
        avg_loss = losers['pnl_pct'].mean()
        expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
        
        gross_profit = winners['pnl_pct'].sum()
        gross_loss = abs(losers['pnl_pct'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        results_sorted = results.sort_values('exit_date')
        results_sorted['cumulative_pnl'] = results_sorted['pnl_pct'].cumsum()
        results_sorted['running_max'] = results_sorted['cumulative_pnl'].cummax()
        results_sorted['drawdown'] = results_sorted['cumulative_pnl'] - results_sorted['running_max']
        max_dd = results_sorted['drawdown'].min()
        
        print(f"  Trades: {len(results)}")
        print(f"  Win rate: {win_rate:.1f}%")
        print(f"  Avg win: {avg_win:+.2f}%")
        print(f"  Avg loss: {avg_loss:+.2f}%")
        print(f"  Expectancy: {expectancy:+.2f}%")
        print(f"  Profit factor: {profit_factor:.2f}")
        print(f"  Max drawdown: {max_dd:.2f}%")
        print()
        
        print("=" * 100)
        print("VERDICT")
        print("=" * 100)
        print()
        
        if expectancy >= 1.20 and profit_factor >= 1.60:
            print("*** REAL SCANNER CODE MATCHES PROVEN RESULTS! ***")
            print()
            print("My 'garbage' backtest WAS garbage!")
            print("Scanner-v3's pattern detection is EXCELLENT!")
        elif expectancy > 0.50:
            print("REAL SCANNER CODE is profitable but weaker than proven results")
            print()
            print("Possible reasons:")
            print("  - Small sample (30 stocks vs 200 in proven test)")
            print("  - Different time period")
            print("  - Missing some patterns/filters")
        else:
            print("REAL SCANNER CODE underperforms")
            print()
            print("Something is wrong with this test - investigate!")
