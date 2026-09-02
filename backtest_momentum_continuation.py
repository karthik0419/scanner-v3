"""
Backtest: Momentum Continuation Strategy vs Scanner-v3

Momentum Continuation Strategy:
1. Stock is in uptrend (20-50% up in last 6 months)
2. Recent pullback (5-10% from 50-day high)
3. Volume surge (2x average on breakout day)
4. Daily gain 2%+ (momentum resumption)
5. Entry: Next day open
6. Stop: 2x ATR below entry (capped at 8%)
7. Target: Previous 50-day high (or 50% of measured move)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

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

def find_momentum_continuation_signals(symbol, start_date, end_date):
    """
    Find momentum continuation signals
    
    Criteria:
    1. 6-month return: 20-50% (strong uptrend but not parabolic)
    2. Pullback: 5-10% from 50-day high (healthy consolidation)
    3. Volume surge: 2x average (institutional interest)
    4. Daily gain: 2%+ (momentum resumption)
    """
    try:
        # Download data with extra buffer for indicators
        buffer_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
        data = yf.download(symbol, start=buffer_start, end=end_date, progress=False)
        
        # Handle multi-index columns from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 200:
            return []
        
        # Calculate indicators
        data['SMA50'] = data['Close'].rolling(window=50).mean()
        data['SMA200'] = data['Close'].rolling(window=200).mean()
        data['High50'] = data['High'].rolling(window=50).max()
        data['AvgVolume'] = data['Volume'].rolling(window=20).mean()
        data['ATR'] = calculate_atr(data, period=14)
        
        # Calculate 6-month return
        data['Return_6M'] = data['Close'].pct_change(periods=126) * 100  # ~6 months
        
        # Calculate pullback from 50-day high
        data['Pullback_pct'] = ((data['High50'] - data['Close']) / data['High50']) * 100
        data['Pullback_pct'] = data['Pullback_pct'].fillna(0)
        
        # Calculate daily gain
        data['Daily_gain'] = data['Close'].pct_change() * 100
        
        # Volume ratio
        data['Volume_ratio'] = data['Volume'] / data['AvgVolume']
        
        # Filter to backtest period
        data = data[data.index >= start_date]
        
        signals = []
        
        for i in range(1, len(data)):
            date = data.index[i]
            
            # Check momentum continuation criteria
            return_6m = data['Return_6M'].iloc[i]
            pullback = data['Pullback_pct'].iloc[i]
            daily_gain = data['Daily_gain'].iloc[i]
            volume_ratio = data['Volume_ratio'].iloc[i]
            close = data['Close'].iloc[i]
            high_50 = data['High50'].iloc[i]
            atr = data['ATR'].iloc[i]
            
            # Skip if any indicator is NaN
            if pd.isna(return_6m) or pd.isna(pullback) or pd.isna(daily_gain) or pd.isna(volume_ratio) or pd.isna(atr):
                continue
            
            # Momentum continuation criteria
            if (20 <= return_6m <= 50 and          # Strong uptrend
                5 <= pullback <= 10 and            # Healthy pullback
                volume_ratio >= 2.0 and            # Volume surge
                daily_gain >= 2.0):                # Momentum resumption
                
                # Entry next day (can't enter same day)
                if i + 1 < len(data):
                    entry_date = data.index[i + 1]
                    entry_price = data['Open'].iloc[i + 1]
                    
                    # Stop loss: 2x ATR below entry, capped at 8%
                    stop_loss_atr = entry_price - (2 * atr)
                    stop_loss_pct = ((entry_price - stop_loss_atr) / entry_price) * 100
                    
                    if stop_loss_pct > 8:
                        stop_loss = entry_price * 0.92  # Cap at 8%
                    else:
                        stop_loss = stop_loss_atr
                    
                    # Target: 50-day high (conservative)
                    target = high_50
                    
                    signals.append({
                        'symbol': symbol,
                        'signal_date': date,
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target': target,
                        'return_6m': return_6m,
                        'pullback': pullback,
                        'daily_gain': daily_gain,
                        'volume_ratio': volume_ratio,
                        'atr': atr
                    })
        
        return signals
    
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return []

def backtest_signal(symbol, entry_date, entry_price, stop_loss, target, end_date):
    """
    Backtest a single signal
    Returns: exit_date, exit_price, exit_reason, pnl_pct
    """
    try:
        # Download data from entry to end
        data = yf.download(symbol, start=entry_date, end=end_date, progress=False)
        
        # Handle multi-index columns from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 2:
            return None, None, 'NO_DATA', 0
        
        # Skip first row (entry day)
        data = data.iloc[1:]
        
        max_hold_days = 45  # Max holding period
        
        for i, (date, row) in enumerate(data.iterrows()):
            # Check stop loss
            if row['Low'] <= stop_loss:
                exit_price = stop_loss
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                return date, exit_price, 'STOP_LOSS', pnl_pct
            
            # Check target
            if row['High'] >= target:
                exit_price = target
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                return date, exit_price, 'TARGET', pnl_pct
            
            # Check max hold period
            if i >= max_hold_days:
                exit_price = row['Close']
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                return date, exit_price, 'TIME_EXIT', pnl_pct
        
        # If loop completes, exit at last available price
        exit_price = data['Close'].iloc[-1]
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        return data.index[-1], exit_price, 'END_OF_DATA', pnl_pct
    
    except Exception as e:
        return None, None, f'ERROR: {e}', 0

def run_backtest(stock_universe, start_date, end_date):
    """
    Run momentum continuation backtest on stock universe
    """
    print("=" * 100)
    print("MOMENTUM CONTINUATION BACKTEST")
    print("=" * 100)
    print(f"Period: {start_date} to {end_date}")
    print(f"Universe: {len(stock_universe)} stocks")
    print()
    print("Criteria:")
    print("  1. 6-month return: 20-50% (strong uptrend)")
    print("  2. Pullback: 5-10% from 50-day high")
    print("  3. Volume surge: 2x average")
    print("  4. Daily gain: 2%+ (momentum resumption)")
    print("  5. Entry: Next day open")
    print("  6. Stop: 2x ATR (capped at 8%)")
    print("  7. Target: 50-day high")
    print("=" * 100)
    print()
    
    all_signals = []
    
    print("Finding signals...")
    for i, symbol in enumerate(stock_universe):
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(stock_universe)} stocks...")
        
        signals = find_momentum_continuation_signals(symbol, start_date, end_date)
        all_signals.extend(signals)
    
    print(f"Found {len(all_signals)} signals")
    print()
    
    if len(all_signals) == 0:
        print("No signals found!")
        return
    
    # Backtest each signal
    print("Backtesting signals...")
    results = []
    
    for i, signal in enumerate(all_signals):
        if (i + 1) % 50 == 0:
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
    
    # Analyze results
    df = pd.DataFrame(results)
    
    if len(df) == 0:
        print("No completed trades!")
        return
    
    # Calculate metrics
    total_trades = len(df)
    winners = df[df['pnl_pct'] > 0]
    losers = df[df['pnl_pct'] < 0]
    
    win_rate = len(winners) / total_trades * 100
    avg_win = winners['pnl_pct'].mean() if len(winners) > 0 else 0
    avg_loss = losers['pnl_pct'].mean() if len(losers) > 0 else 0
    avg_pnl = df['pnl_pct'].mean()
    
    # Expectancy
    expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
    
    # Profit factor
    gross_profit = winners['pnl_pct'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Max drawdown (simplified)
    df = df.sort_values('exit_date')
    df['cumulative_pnl'] = df['pnl_pct'].cumsum()
    df['running_max'] = df['cumulative_pnl'].cummax()
    df['drawdown'] = df['cumulative_pnl'] - df['running_max']
    max_drawdown = df['drawdown'].min()
    
    # Print results
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
    
    # Exit reason breakdown
    print("Exit reasons:")
    for reason, count in df['exit_reason'].value_counts().items():
        pct = count / total_trades * 100
        avg_pnl_reason = df[df['exit_reason'] == reason]['pnl_pct'].mean()
        print(f"  {reason:15} {count:4} ({pct:5.1f}%) | Avg P&L: {avg_pnl_reason:+.2f}%")
    print()
    
    # Best and worst trades
    print("Best trades:")
    best = df.nlargest(5, 'pnl_pct')[['symbol', 'entry_date', 'exit_date', 'pnl_pct', 'exit_reason']]
    for _, row in best.iterrows():
        print(f"  {row['symbol']:15} {row['entry_date'].strftime('%Y-%m-%d')} -> {row['exit_date'].strftime('%Y-%m-%d')} | {row['pnl_pct']:+6.2f}% | {row['exit_reason']}")
    print()
    
    print("Worst trades:")
    worst = df.nsmallest(5, 'pnl_pct')[['symbol', 'entry_date', 'exit_date', 'pnl_pct', 'exit_reason']]
    for _, row in worst.iterrows():
        print(f"  {row['symbol']:15} {row['entry_date'].strftime('%Y-%m-%d')} -> {row['exit_date'].strftime('%Y-%m-%d')} | {row['pnl_pct']:+6.2f}% | {row['exit_reason']}")
    print()
    
    # Save results
    output_file = f'results/momentum_continuation_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    print()
    
    return df

if __name__ == '__main__':
    # Load stock universe (use backbone50 for quick test, nifty200 for full test)
    print("Loading stock universe...")
    
    # Try test universe first
    try:
        with open('temp/test_universe.txt', 'r') as f:
            stocks = [line.strip() + '.NS' for line in f if line.strip() and not line.startswith('#')]
        print(f"Loaded {len(stocks)} stocks from temp/test_universe.txt")
    except:
        # Fallback to nifty200
        try:
            with open('nifty200.txt', 'r') as f:
                stocks = [line.strip() + '.NS' for line in f if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(stocks)} stocks from nifty200.txt")
        except:
            print("ERROR: Could not load stock universe!")
            print("Please ensure temp/test_universe.txt or nifty200.txt exists")
            exit(1)
    
    # Backtest period: Last 5 years
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
    
    # Run backtest
    results = run_backtest(stocks, start_date, end_date)
    
    print()
    print("=" * 100)
    print("COMPARISON TO SCANNER-V3")
    print("=" * 100)
    print()
    print("Scanner-v3 (from AGENTS.md):")
    print("  Trades: 3012")
    print("  Win rate: 40.6%")
    print("  Avg win: +7.6%")
    print("  Avg loss: -3.0%")
    print("  Expectancy: +1.30%")
    print("  Profit factor: 1.73")
    print("  Max drawdown: -60.1%")
    print()
    
    if results is not None and len(results) > 0:
        print("Momentum Continuation:")
        print(f"  Trades: {len(results)}")
        print(f"  Win rate: {len(results[results['pnl_pct'] > 0]) / len(results) * 100:.1f}%")
        print(f"  Avg win: {results[results['pnl_pct'] > 0]['pnl_pct'].mean():+.2f}%")
        print(f"  Avg loss: {results[results['pnl_pct'] < 0]['pnl_pct'].mean():+.2f}%")
        
        win_rate = len(results[results['pnl_pct'] > 0]) / len(results) * 100
        avg_win = results[results['pnl_pct'] > 0]['pnl_pct'].mean()
        avg_loss = results[results['pnl_pct'] < 0]['pnl_pct'].mean()
        expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
        
        print(f"  Expectancy: {expectancy:+.2f}%")
        
        gross_profit = results[results['pnl_pct'] > 0]['pnl_pct'].sum()
        gross_loss = abs(results[results['pnl_pct'] < 0]['pnl_pct'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        print(f"  Profit factor: {profit_factor:.2f}")
        
        results_sorted = results.sort_values('exit_date')
        results_sorted['cumulative_pnl'] = results_sorted['pnl_pct'].cumsum()
        results_sorted['running_max'] = results_sorted['cumulative_pnl'].cummax()
        results_sorted['drawdown'] = results_sorted['cumulative_pnl'] - results_sorted['running_max']
        max_dd = results_sorted['drawdown'].min()
        
        print(f"  Max drawdown: {max_dd:.2f}%")
        print()
        
        # Verdict
        print("=" * 100)
        print("VERDICT")
        print("=" * 100)
        
        if expectancy > 1.30:
            print("Momentum Continuation BEATS Scanner-v3 on expectancy!")
        elif expectancy > 0:
            print("Momentum Continuation is profitable but WEAKER than Scanner-v3")
        else:
            print("Momentum Continuation LOSES MONEY - DO NOT USE!")
