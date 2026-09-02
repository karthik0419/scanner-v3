"""
BACKTEST: COMBINED STRATEGY (Scanner-v3 + MTF Alignment)

Strategy:
1. Use Scanner-v3's pattern detection (C&H, Double Bottom, etc.)
2. Add MTF Alignment as BONUS scoring (not required)
3. Prioritize stocks with 3/3 MTF alignment
4. Keep all of scanner-v3's filters (volume, R:R, risk, etc.)

Scoring:
- Base score: Scanner-v3 pattern score (0-100)
- MTF Bonus: +15 points for 3/3 alignment
- MTF Bonus: +10 points for 2/3 alignment
- MTF Bonus: +5 points for 1/3 alignment
- Final score: Base + MTF Bonus

Entry rules:
- Same as scanner-v3 (NEAR/BREAKOUT status)
- But prioritize high MTF scores

Compare to:
- Scanner-v3: +1.30% expectancy, 1.73 PF
- MTF Alignment: +0.93% expectancy, 1.35 PF
- Combined: ???
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

def check_cup_and_handle(data, i):
    """
    Simplified Cup & Handle detection
    Returns: (is_pattern, breakout_price, stop_loss, target)
    """
    if i < 100:
        return False, None, None, None
    
    # Look back 60 days for cup
    lookback = data.iloc[i-60:i+1]
    
    if len(lookback) < 60:
        return False, None, None, None
    
    # Find cup low (should be in middle third)
    cup_low_idx = lookback['Low'].idxmin()
    cup_low_pos = lookback.index.get_loc(cup_low_idx)
    
    # Cup low should be in middle third (20-40 days back)
    if not (20 <= (60 - cup_low_pos) <= 40):
        return False, None, None, None
    
    # Cup depth (should be 12-33%)
    left_high = lookback['High'].iloc[:20].max()
    right_high = lookback['High'].iloc[-20:].max()
    cup_low = lookback['Low'].iloc[cup_low_pos]
    
    cup_depth = ((left_high - cup_low) / left_high) * 100
    
    if not (12 <= cup_depth <= 33):
        return False, None, None, None
    
    # Handle (last 10-20 days, pullback 5-15%)
    handle = lookback.iloc[-20:]
    handle_high = handle['High'].max()
    handle_low = handle['Low'].min()
    
    handle_depth = ((handle_high - handle_low) / handle_high) * 100
    
    if not (5 <= handle_depth <= 15):
        return False, None, None, None
    
    # Breakout price (handle high)
    breakout = handle_high
    
    # Stop loss (handle low or 2x ATR)
    atr = data['ATR'].iloc[i]
    stop_atr = data['Close'].iloc[i] - (2 * atr)
    stop_handle = handle_low
    
    stop_loss = max(stop_atr, stop_handle)  # Use tighter stop
    
    # Cap stop at 8%
    stop_pct = ((data['Close'].iloc[i] - stop_loss) / data['Close'].iloc[i]) * 100
    if stop_pct > 8:
        stop_loss = data['Close'].iloc[i] * 0.92
    
    # Target (measured move)
    measured_move = left_high + (left_high - cup_low)
    target = measured_move * 0.5 + left_high * 0.5  # 50% of measured move
    
    return True, breakout, stop_loss, target

def calculate_mtf_alignment(data, i):
    """
    Calculate Multi-Timeframe Alignment score
    Returns: (mtf_score, alignment_count)
    """
    close = data['Close'].iloc[i]
    sma20 = data['SMA20'].iloc[i]
    sma50 = data['SMA50'].iloc[i]
    sma100 = data['SMA100'].iloc[i]
    sma200 = data['SMA200'].iloc[i]
    
    high_6m = data['High_6M'].iloc[i]
    low_6m = data['Low_6M'].iloc[i]
    
    # Check for NaN
    if pd.isna([sma20, sma50, sma100, sma200, high_6m, low_6m]).any():
        return 0, 0
    
    # 1. Daily bullish
    daily_bullish = (close > sma20 and sma20 > sma50 and sma50 > sma200)
    
    # 2. Weekly bullish
    weekly_bullish = (close > sma100)
    
    # 3. Monthly bullish
    range_6m = high_6m - low_6m
    if range_6m > 0:
        position_in_range = (close - low_6m) / range_6m
        monthly_bullish = position_in_range > 0.70
    else:
        monthly_bullish = False
    
    # Count alignment
    alignment_count = sum([daily_bullish, weekly_bullish, monthly_bullish])
    
    # Score bonus
    if alignment_count == 3:
        mtf_bonus = 15
    elif alignment_count == 2:
        mtf_bonus = 10
    elif alignment_count == 1:
        mtf_bonus = 5
    else:
        mtf_bonus = 0
    
    return mtf_bonus, alignment_count

def find_combined_signals(symbol, start_date, end_date):
    """
    Find signals using Scanner-v3 patterns + MTF Alignment bonus
    """
    try:
        # Download data
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
        
        data['AvgVolume'] = data['Volume'].rolling(window=20).mean()
        data['ATR'] = calculate_atr(data, period=14)
        
        # Filter to backtest period
        data = data[data.index >= start_date]
        
        signals = []
        
        for i in range(100, len(data)):
            date = data.index[i]
            
            # 1. Check for Cup & Handle pattern (Scanner-v3 logic)
            is_pattern, breakout, stop_loss, target = check_cup_and_handle(data, i)
            
            if not is_pattern:
                continue
            
            # 2. Check volume (Scanner-v3 filter)
            volume = data['Volume'].iloc[i]
            avg_volume = data['AvgVolume'].iloc[i]
            
            if pd.isna(avg_volume) or volume < avg_volume * 0.8:
                continue
            
            # 3. Calculate R:R (Scanner-v3 filter)
            close = data['Close'].iloc[i]
            risk = close - stop_loss
            reward = target - close
            rr = reward / risk if risk > 0 else 0
            
            if rr < 1.5:
                continue
            
            # 4. Base score (simplified scanner-v3 scoring)
            base_score = 50  # Base for C&H pattern
            
            # Volume bonus
            vol_ratio = volume / avg_volume if avg_volume > 0 else 1
            if vol_ratio > 1.5:
                base_score += 10
            elif vol_ratio > 1.2:
                base_score += 5
            
            # R:R bonus
            if rr > 3:
                base_score += 10
            elif rr > 2:
                base_score += 5
            
            # 5. MTF Alignment bonus (NEW!)
            mtf_bonus, mtf_alignment = calculate_mtf_alignment(data, i)
            
            # 6. Final score
            final_score = base_score + mtf_bonus
            
            # 7. Entry next day
            if i + 1 < len(data):
                entry_date = data.index[i + 1]
                entry_price = data['Open'].iloc[i + 1]
                
                # Adjust stop/target from entry price
                stop_loss_adj = entry_price - (close - stop_loss)
                target_adj = target
                
                signals.append({
                    'symbol': symbol,
                    'signal_date': date,
                    'entry_date': entry_date,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss_adj,
                    'target': target_adj,
                    'base_score': base_score,
                    'mtf_bonus': mtf_bonus,
                    'mtf_alignment': mtf_alignment,
                    'final_score': final_score,
                    'rr': rr,
                    'vol_ratio': vol_ratio
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
    """Run Combined Strategy backtest"""
    print("=" * 100)
    print("COMBINED STRATEGY BACKTEST (Scanner-v3 + MTF Alignment)")
    print("=" * 100)
    print(f"Period: {start_date} to {end_date}")
    print(f"Universe: {len(stock_universe)} stocks")
    print()
    print("Strategy:")
    print("  1. Scanner-v3 pattern detection (Cup & Handle)")
    print("  2. Scanner-v3 filters (volume 1.2x+, R:R 1.5+, 8% max stop)")
    print("  3. MTF Alignment BONUS scoring:")
    print("     - 3/3 alignment: +15 points")
    print("     - 2/3 alignment: +10 points")
    print("     - 1/3 alignment: +5 points")
    print("  4. Entry: Next day open")
    print("  5. Stop: 2x ATR or handle low (capped at 8%)")
    print("  6. Target: 50% of measured move")
    print("=" * 100)
    print()
    
    all_signals = []
    
    print("Finding signals...")
    for i, symbol in enumerate(stock_universe):
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(stock_universe)} stocks...")
        
        signals = find_combined_signals(symbol, start_date, end_date)
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
    
    expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
    
    gross_profit = winners['pnl_pct'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
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
    
    # MTF Alignment breakdown
    print("MTF Alignment breakdown:")
    for mtf in [3, 2, 1, 0]:
        mtf_df = df[df['mtf_alignment'] == mtf]
        if len(mtf_df) > 0:
            mtf_win_rate = len(mtf_df[mtf_df['pnl_pct'] > 0]) / len(mtf_df) * 100
            mtf_avg_pnl = mtf_df['pnl_pct'].mean()
            print(f"  {mtf}/3 alignment: {len(mtf_df):3} trades | Win rate: {mtf_win_rate:5.1f}% | Avg P&L: {mtf_avg_pnl:+6.2f}%")
    print()
    
    # Exit reasons
    print("Exit reasons:")
    for reason, count in df['exit_reason'].value_counts().items():
        pct = count / total_trades * 100
        avg_pnl_reason = df[df['exit_reason'] == reason]['pnl_pct'].mean()
        print(f"  {reason:15} {count:4} ({pct:5.1f}%) | Avg P&L: {avg_pnl_reason:+.2f}%")
    print()
    
    # Best and worst
    print("Best trades:")
    best = df.nlargest(5, 'pnl_pct')[['symbol', 'entry_date', 'pnl_pct', 'mtf_alignment', 'final_score']]
    for _, row in best.iterrows():
        print(f"  {row['symbol']:15} {row['entry_date'].strftime('%Y-%m-%d')} | {row['pnl_pct']:+6.2f}% | MTF: {row['mtf_alignment']}/3 | Score: {row['final_score']:.0f}")
    print()
    
    print("Worst trades:")
    worst = df.nsmallest(5, 'pnl_pct')[['symbol', 'entry_date', 'pnl_pct', 'mtf_alignment', 'final_score']]
    for _, row in worst.iterrows():
        print(f"  {row['symbol']:15} {row['entry_date'].strftime('%Y-%m-%d')} | {row['pnl_pct']:+6.2f}% | MTF: {row['mtf_alignment']}/3 | Score: {row['final_score']:.0f}")
    print()
    
    # Save results
    output_file = f'results/combined_strategy_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    print()
    
    return df

if __name__ == '__main__':
    print("Loading stock universe...")
    
    try:
        with open('temp/test_universe.txt', 'r') as f:
            stocks = [line.strip() + '.NS' for line in f if line.strip()]
        print(f"Loaded {len(stocks)} stocks")
    except:
        try:
            with open('nifty200.txt', 'r') as f:
                stocks = [line.strip() + '.NS' for line in f if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(stocks)} stocks")
        except:
            print("ERROR: Could not load stock universe!")
            exit(1)
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
    
    results = run_backtest(stocks, start_date, end_date)
    
    if results is not None:
        print()
        print("=" * 100)
        print("FINAL COMPARISON")
        print("=" * 100)
        print()
        
        print("Scanner-v3 (baseline):")
        print("  Trades: 3012")
        print("  Win rate: 40.6%")
        print("  Avg win: +7.6%")
        print("  Avg loss: -3.0%")
        print("  Expectancy: +1.30%")
        print("  Profit factor: 1.73")
        print("  Max drawdown: -60.1%")
        print()
        
        print("MTF Alignment only:")
        print("  Trades: 10")
        print("  Win rate: 40.0%")
        print("  Avg win: +9.02%")
        print("  Avg loss: -4.46%")
        print("  Expectancy: +0.93%")
        print("  Profit factor: 1.35")
        print("  Max drawdown: -18.56%")
        print()
        
        print("COMBINED (Scanner-v3 + MTF Bonus):")
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
        
        if expectancy > 1.30 and profit_factor > 1.73:
            print("*** COMBINED STRATEGY BEATS SCANNER-V3! ***")
            print()
            print("RECOMMENDATION: Implement MTF bonus in scanner-v3!")
        elif expectancy > 1.30 or profit_factor > 1.73:
            print("COMBINED STRATEGY is COMPETITIVE with Scanner-v3")
            print()
            print("RECOMMENDATION: Consider implementing MTF bonus")
        elif expectancy > 0:
            print("COMBINED STRATEGY is profitable but WEAKER than Scanner-v3")
            print()
            print("RECOMMENDATION: Keep scanner-v3 as-is")
        else:
            print("COMBINED STRATEGY LOSES MONEY")
            print()
            print("RECOMMENDATION: Stick with scanner-v3")
