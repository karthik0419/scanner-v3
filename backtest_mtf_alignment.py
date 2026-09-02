"""
BACKTEST: Multi-Timeframe Alignment Strategy (5 Years)

Strategy:
1. Multi-Timeframe Alignment (3/3):
   - Daily: Close > SMA20 > SMA50 > SMA200
   - Weekly: Close > SMA100 (20-week equivalent)
   - Monthly: Price in upper 30% of 6-month range
2. Momentum Continuation (20-40% into the move):
   - 3-month return between 20-40%
3. Pattern: Cup & Handle or consolidation near highs
4. Entry: Next day open
5. Stop: 2x ATR (capped at 8%)
6. Target: 6-month high OR 50% of measured move
7. Max hold: 45 days

Compare to:
- Scanner-v3: +1.30% expectancy, 1.73 PF, 40.6% win rate
- Momentum Continuation: -0.27% expectancy, 0.92 PF, 44.4% win rate
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

def find_mtf_signals(symbol, start_date, end_date):
    """
    Find Multi-Timeframe Alignment signals
    
    Criteria:
    1. Daily bullish: Close > SMA20 > SMA50 > SMA200
    2. Weekly bullish: Close > SMA100
    3. Monthly bullish: Price in upper 30% of 6M range
    4. Momentum: 3M return between 20-40% (sweet spot)
    5. Near highs: Within 10% of 20-day high
    6. Volume: Above average
    """
    try:
        # Download data with buffer
        buffer_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
        data = yf.download(symbol, start=buffer_start, end=end_date, progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 250:
            return []
        
        # Calculate indicators
        data['SMA20'] = data['Close'].rolling(window=20).mean()
        data['SMA50'] = data['Close'].rolling(window=50).mean()
        data['SMA100'] = data['Close'].rolling(window=100).mean()
        data['SMA200'] = data['Close'].rolling(window=200).mean()
        
        data['High_6M'] = data['High'].rolling(window=126).max()
        data['Low_6M'] = data['Low'].rolling(window=126).min()
        data['High_20D'] = data['High'].rolling(window=20).max()
        
        data['AvgVolume'] = data['Volume'].rolling(window=20).mean()
        data['ATR'] = calculate_atr(data, period=14)
        
        # Calculate returns
        data['Return_3M'] = data['Close'].pct_change(periods=60) * 100
        
        # Filter to backtest period
        data = data[data.index >= start_date]
        
        signals = []
        
        for i in range(1, len(data)):
            date = data.index[i]
            
            close = data['Close'].iloc[i]
            sma20 = data['SMA20'].iloc[i]
            sma50 = data['SMA50'].iloc[i]
            sma100 = data['SMA100'].iloc[i]
            sma200 = data['SMA200'].iloc[i]
            
            high_6m = data['High_6M'].iloc[i]
            low_6m = data['Low_6M'].iloc[i]
            high_20d = data['High_20D'].iloc[i]
            
            volume = data['Volume'].iloc[i]
            avg_volume = data['AvgVolume'].iloc[i]
            atr = data['ATR'].iloc[i]
            
            return_3m = data['Return_3M'].iloc[i]
            
            # Skip if any indicator is NaN
            if pd.isna([sma20, sma50, sma100, sma200, high_6m, low_6m, atr, return_3m]).any():
                continue
            
            # 1. DAILY TREND: Close > SMA20 > SMA50 > SMA200
            daily_bullish = (close > sma20 and sma20 > sma50 and sma50 > sma200)
            
            # 2. WEEKLY TREND: Close > SMA100
            weekly_bullish = (close > sma100)
            
            # 3. MONTHLY TREND: Price in upper 30% of 6M range
            range_6m = high_6m - low_6m
            if range_6m > 0:
                position_in_range = (close - low_6m) / range_6m
                monthly_bullish = position_in_range > 0.70
            else:
                monthly_bullish = False
            
            # MTF Alignment: All 3 must be true
            mtf_aligned = daily_bullish and weekly_bullish and monthly_bullish
            
            if not mtf_aligned:
                continue
            
            # 4. MOMENTUM: 3M return between 20-40% (sweet spot)
            momentum_sweet_spot = (20 <= return_3m <= 40)
            
            if not momentum_sweet_spot:
                continue
            
            # 5. NEAR HIGHS: Within 10% of 20-day high
            distance_from_high = ((high_20d - close) / high_20d) * 100
            near_highs = distance_from_high < 10
            
            if not near_highs:
                continue
            
            # 6. VOLUME: Above average
            volume_ok = volume > avg_volume * 0.8  # At least 80% of average
            
            if not volume_ok:
                continue
            
            # Entry next day
            if i + 1 < len(data):
                entry_date = data.index[i + 1]
                entry_price = data['Open'].iloc[i + 1]
                
                # Stop loss: 2x ATR, capped at 8%
                stop_loss_atr = entry_price - (2 * atr)
                stop_loss_pct = ((entry_price - stop_loss_atr) / entry_price) * 100
                
                if stop_loss_pct > 8:
                    stop_loss = entry_price * 0.92  # Cap at 8%
                else:
                    stop_loss = stop_loss_atr
                
                # Target: 6-month high
                target = high_6m
                
                # Calculate R:R
                risk = entry_price - stop_loss
                reward = target - entry_price
                rr = reward / risk if risk > 0 else 0
                
                # Only take trades with R:R >= 1.5
                if rr < 1.5:
                    continue
                
                signals.append({
                    'symbol': symbol,
                    'signal_date': date,
                    'entry_date': entry_date,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'target': target,
                    'return_3m': return_3m,
                    'distance_from_high': distance_from_high,
                    'rr': rr,
                    'atr': atr
                })
        
        return signals
    
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return []

def backtest_signal(symbol, entry_date, entry_price, stop_loss, target, end_date):
    """
    Backtest a single signal
    """
    try:
        data = yf.download(symbol, start=entry_date, end=end_date, progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 2:
            return None, None, 'NO_DATA', 0
        
        # Skip first row (entry day)
        data = data.iloc[1:]
        
        max_hold_days = 45
        
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
        
        # Exit at last available price
        exit_price = data['Close'].iloc[-1]
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        return data.index[-1], exit_price, 'END_OF_DATA', pnl_pct
    
    except Exception as e:
        return None, None, f'ERROR: {e}', 0

def run_backtest(stock_universe, start_date, end_date):
    """
    Run Multi-Timeframe Alignment backtest
    """
    print("=" * 100)
    print("MULTI-TIMEFRAME ALIGNMENT BACKTEST (5 YEARS)")
    print("=" * 100)
    print(f"Period: {start_date} to {end_date}")
    print(f"Universe: {len(stock_universe)} stocks")
    print()
    print("Strategy:")
    print("  1. Multi-Timeframe Alignment (3/3):")
    print("     - Daily: Close > SMA20 > SMA50 > SMA200")
    print("     - Weekly: Close > SMA100")
    print("     - Monthly: Price in upper 30% of 6M range")
    print("  2. Momentum: 3M return 20-40% (sweet spot)")
    print("  3. Near highs: Within 10% of 20-day high")
    print("  4. Volume: Above 80% of average")
    print("  5. Entry: Next day open")
    print("  6. Stop: 2x ATR (capped at 8%)")
    print("  7. Target: 6-month high")
    print("  8. R:R: Minimum 1.5:1")
    print("=" * 100)
    print()
    
    all_signals = []
    
    print("Finding signals...")
    for i, symbol in enumerate(stock_universe):
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(stock_universe)} stocks...")
        
        signals = find_mtf_signals(symbol, start_date, end_date)
        all_signals.extend(signals)
    
    print(f"Found {len(all_signals)} signals")
    print()
    
    if len(all_signals) == 0:
        print("No signals found!")
        return None
    
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
        return None
    
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
    
    # Max drawdown
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
    output_file = f'results/mtf_alignment_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    print()
    
    return df

if __name__ == '__main__':
    # Load stock universe
    print("Loading stock universe...")
    
    try:
        with open('temp/test_universe.txt', 'r') as f:
            stocks = [line.strip() + '.NS' for line in f if line.strip()]
        print(f"Loaded {len(stocks)} stocks from temp/test_universe.txt")
    except:
        try:
            with open('nifty200.txt', 'r') as f:
                stocks = [line.strip() + '.NS' for line in f if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(stocks)} stocks from nifty200.txt")
        except:
            print("ERROR: Could not load stock universe!")
            exit(1)
    
    # Backtest period: Last 5 years
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
    
    # Run backtest
    results = run_backtest(stocks, start_date, end_date)
    
    if results is not None:
        print()
        print("=" * 100)
        print("COMPARISON")
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
        
        print("Momentum Continuation (tested earlier):")
        print("  Trades: 18")
        print("  Win rate: 44.4%")
        print("  Avg win: +6.71%")
        print("  Avg loss: -5.86%")
        print("  Expectancy: -0.27%")
        print("  Profit factor: 0.92")
        print("  Max drawdown: -31.15%")
        print()
        
        print("Multi-Timeframe Alignment (this test):")
        print(f"  Trades: {len(results)}")
        
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
        
        print(f"  Win rate: {win_rate:.1f}%")
        print(f"  Avg win: {avg_win:+.2f}%")
        print(f"  Avg loss: {avg_loss:+.2f}%")
        print(f"  Expectancy: {expectancy:+.2f}%")
        print(f"  Profit factor: {profit_factor:.2f}")
        print(f"  Max drawdown: {max_dd:.2f}%")
        print()
        
        # Verdict
        print("=" * 100)
        print("VERDICT")
        print("=" * 100)
        print()
        
        if expectancy > 1.30:
            print("*** MULTI-TIMEFRAME ALIGNMENT BEATS SCANNER-V3! ***")
            print()
            print("RECOMMENDATION: Implement MTF filter in scanner-v3!")
        elif expectancy > 0:
            print("Multi-Timeframe Alignment is PROFITABLE but WEAKER than Scanner-v3")
            print()
            print("RECOMMENDATION: Keep scanner-v3 as-is, MTF doesn't add value")
        else:
            print("Multi-Timeframe Alignment LOSES MONEY - DO NOT USE!")
            print()
            print("RECOMMENDATION: Stick with scanner-v3")
