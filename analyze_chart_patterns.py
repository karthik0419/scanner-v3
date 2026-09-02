"""
CHART PATTERN ANALYSIS: What did the diagrams/annotations show?

From the chart images you provided, let me analyze what VISUAL PATTERNS
were marked that the scanner might have missed:

Key observations from your charts:
1. Chennai Petro: "Almost 40% journey done in 3 months" - MOMENTUM CONTINUATION
2. Anthem: Multiple timeframes (Weekly + Daily) showing C&H - MULTI-TIMEFRAME CONFIRMATION
3. Balrampur Chini: "35% Move From Our Zone" - ALREADY RUNNING
4. Tilaknagar: "Almost 30% up from our levels" - ALREADY RUNNING
5. EPL: Clean monthly C&H with measured move - CLASSICAL PATTERN
6. Varroc: "Profit Booking Area 900-1000" - TARGET ZONE MARKED
7. Brigade: "2x Upside Potential" - LARGE MEASURED MOVE
8. Concord: "2x Journey Started" - EARLY STAGE BREAKOUT

HYPOTHESIS: The charts worked because they showed:
1. MULTI-TIMEFRAME ALIGNMENT (Daily + Weekly + Monthly all bullish)
2. MEASURED MOVES (Clear target zones marked)
3. MOMENTUM ALREADY STARTED (Not waiting for breakout)
4. VISUAL CONFIRMATION (Clean patterns, not messy)

Let's test if these visual factors predict success better than smart money
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def analyze_chart_pattern_quality(symbol, analysis_date='2026-08-22'):
    """
    Analyze the VISUAL QUALITY of chart patterns
    (What a human trader sees that algorithms miss)
    """
    try:
        # Download 2 years of data for multi-timeframe analysis
        end_date = datetime.strptime(analysis_date, '%Y-%m-%d')
        start_date = end_date - timedelta(days=730)  # 2 years
        
        data = yf.download(symbol, start=start_date.strftime('%Y-%m-%d'), 
                          end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 200:
            return None
        
        # Calculate multi-timeframe indicators
        # Daily
        data['SMA20_D'] = data['Close'].rolling(window=20).mean()
        data['SMA50_D'] = data['Close'].rolling(window=50).mean()
        data['SMA200_D'] = data['Close'].rolling(window=200).mean()
        
        # Weekly (approximate with 5-day rolling)
        data['SMA20_W'] = data['Close'].rolling(window=100).mean()  # ~20 weeks
        data['SMA50_W'] = data['Close'].rolling(window=250).mean()  # ~50 weeks
        
        # Monthly (approximate with 20-day rolling)
        data['High_6M'] = data['High'].rolling(window=126).max()  # 6 months
        data['Low_6M'] = data['Low'].rolling(window=126).min()
        
        last = data.iloc[-1]
        
        # 1. MULTI-TIMEFRAME ALIGNMENT
        # Daily trend
        daily_bullish = (last['Close'] > last['SMA20_D'] and 
                        last['SMA20_D'] > last['SMA50_D'] and
                        last['SMA50_D'] > last['SMA200_D'])
        
        # Weekly trend (using longer SMAs)
        weekly_bullish = (last['Close'] > last['SMA20_W'] and 
                         last['SMA20_W'] > last['SMA50_W'])
        
        # Monthly trend (price in upper half of 6M range)
        range_6m = last['High_6M'] - last['Low_6M']
        position_in_range = ((last['Close'] - last['Low_6M']) / range_6m) * 100 if range_6m > 0 else 50
        monthly_bullish = position_in_range > 70  # In upper 30% of 6M range
        
        mtf_alignment = sum([daily_bullish, weekly_bullish, monthly_bullish])
        
        # 2. MOMENTUM ALREADY STARTED (Not waiting for breakout)
        # Check if price has already moved significantly
        return_1m = ((last['Close'] - data['Close'].iloc[-20]) / data['Close'].iloc[-20]) * 100 if len(data) >= 20 else 0
        return_3m = ((last['Close'] - data['Close'].iloc[-60]) / data['Close'].iloc[-60]) * 100 if len(data) >= 60 else 0
        return_6m = ((last['Close'] - data['Close'].iloc[-126]) / data['Close'].iloc[-126]) * 100 if len(data) >= 126 else 0
        
        momentum_started = (return_1m > 5 or return_3m > 15 or return_6m > 25)
        
        # 3. PATTERN CLEANLINESS (Low volatility = clean pattern)
        recent_60d = data.tail(60)
        returns = recent_60d['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized
        
        clean_pattern = volatility < 40  # Low volatility = clean
        
        # 4. MEASURED MOVE POTENTIAL (Distance to 6M high)
        distance_to_6m_high = ((last['High_6M'] - last['Close']) / last['Close']) * 100
        large_measured_move = distance_to_6m_high > 20  # 20%+ upside to 6M high
        
        # 5. BREAKOUT CONFIRMATION (Already above key levels)
        above_sma50 = last['Close'] > last['SMA50_D']
        above_sma200 = last['Close'] > last['SMA200_D']
        
        breakout_confirmed = above_sma50 and above_sma200
        
        # 6. VOLUME TREND (Increasing volume = institutional interest)
        vol_20d = data['Volume'].tail(20).mean()
        vol_60d = data['Volume'].tail(60).mean()
        volume_increasing = vol_20d > vol_60d * 1.2
        
        # 7. HIGHER LOWS (Sign of accumulation)
        lows_20d = recent_60d['Low'].tail(20)
        lows_40d = recent_60d['Low'].tail(40).head(20)
        higher_lows = lows_20d.min() > lows_40d.min()
        
        # VISUAL PATTERN SCORE (0-100)
        score = 0
        
        # Multi-timeframe alignment (30 points)
        score += mtf_alignment * 10
        
        # Momentum already started (20 points)
        if momentum_started:
            score += 20
        
        # Pattern cleanliness (15 points)
        if clean_pattern:
            score += 15
        
        # Large measured move (15 points)
        if large_measured_move:
            score += 15
        
        # Breakout confirmed (10 points)
        if breakout_confirmed:
            score += 10
        
        # Volume increasing (5 points)
        if volume_increasing:
            score += 5
        
        # Higher lows (5 points)
        if higher_lows:
            score += 5
        
        return {
            'symbol': symbol,
            'close': last['Close'],
            'mtf_alignment': mtf_alignment,
            'daily_bullish': daily_bullish,
            'weekly_bullish': weekly_bullish,
            'monthly_bullish': monthly_bullish,
            'momentum_started': momentum_started,
            'return_1m': return_1m,
            'return_3m': return_3m,
            'return_6m': return_6m,
            'clean_pattern': clean_pattern,
            'volatility': volatility,
            'large_measured_move': large_measured_move,
            'distance_to_6m_high': distance_to_6m_high,
            'breakout_confirmed': breakout_confirmed,
            'volume_increasing': volume_increasing,
            'higher_lows': higher_lows,
            'visual_pattern_score': score
        }
    
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

def main():
    print("=" * 100)
    print("CHART PATTERN ANALYSIS: What Did The Diagrams Show?")
    print("=" * 100)
    print()
    print("Analyzing VISUAL PATTERNS that humans see but algorithms miss:")
    print("  1. Multi-timeframe alignment (Daily + Weekly + Monthly)")
    print("  2. Momentum already started (not waiting for breakout)")
    print("  3. Pattern cleanliness (low volatility)")
    print("  4. Large measured moves (big upside potential)")
    print("  5. Breakout confirmation (above key levels)")
    print("=" * 100)
    print()
    
    # Your chart picks with annotations
    stocks = {
        # WINNERS
        'CHENNPETRO.NS': {
            'profit': 33.75,
            'chart_annotation': 'Almost 40% journey done in 3 months',
            'pattern_type': 'Momentum Continuation'
        },
        'ANTHEM.NS': {
            'profit': 20.33,
            'chart_annotation': 'Weekly + Daily C&H, Upside 820-850',
            'pattern_type': 'Multi-timeframe C&H'
        },
        'VARROC.NS': {
            'profit': 19.99,
            'chart_annotation': 'Profit Booking Area 900-1000',
            'pattern_type': 'Monthly C&H with target'
        },
        'BRIGADE.NS': {
            'profit': 2.17,
            'chart_annotation': '2x Upside Potential',
            'pattern_type': 'Monthly C&H'
        },
        'ACE.NS': {
            'profit': 0.82,
            'chart_annotation': '20% Move, 30 Left',
            'pattern_type': 'Weekly C&H'
        },
        'CONCORDBIO.NS': {
            'profit': 0.36,
            'chart_annotation': '2x Journey Started',
            'pattern_type': 'Weekly C&H'
        },
        'BALUFORGE.NS': {
            'profit': 0.00,
            'chart_annotation': '35% Move From Our Zone',
            'pattern_type': 'Weekly C&H'
        },
        
        # LOSERS
        'BALRAMCHIN.NS': {
            'profit': -0.78,
            'chart_annotation': '35% Move From Our Zone',
            'pattern_type': 'Weekly C&H'
        },
        'EPL.NS': {
            'profit': -0.00,
            'chart_annotation': 'Upside Range 370-400',
            'pattern_type': 'Monthly C&H'
        },
        'MANALIPETC.NS': {
            'profit': -0.00,
            'chart_annotation': '128.88% upside, 150% potential',
            'pattern_type': 'Monthly C&H'
        },
        'JTLIND.NS': {
            'profit': -0.00,
            'chart_annotation': 'Upside Potential 110-120',
            'pattern_type': 'Weekly C&H'
        },
    }
    
    print("Analyzing visual pattern quality...")
    print()
    
    results = []
    for symbol, info in stocks.items():
        analysis = analyze_chart_pattern_quality(symbol, '2026-08-22')
        if analysis:
            analysis['actual_profit'] = info['profit']
            analysis['chart_annotation'] = info['chart_annotation']
            analysis['pattern_type'] = info['pattern_type']
            results.append(analysis)
    
    df = pd.DataFrame(results)
    df = df.sort_values('visual_pattern_score', ascending=False)
    
    print("=" * 100)
    print("VISUAL PATTERN SCORES vs ACTUAL PERFORMANCE")
    print("=" * 100)
    print()
    
    print(f"{'Stock':<15} {'Visual':<8} {'Profit':<8} {'MTF':<5} {'Momentum':<10} {'Clean':<7} {'Annotation':<30}")
    print("-" * 100)
    
    for _, row in df.iterrows():
        symbol_short = row['symbol'].replace('.NS', '')
        visual_score = row['visual_pattern_score']
        profit = row['actual_profit']
        mtf = f"{row['mtf_alignment']}/3"
        momentum = "YES" if row['momentum_started'] else "NO"
        clean = "YES" if row['clean_pattern'] else "NO"
        annotation = row['chart_annotation'][:28]
        
        print(f"{symbol_short:<15} {visual_score:<8.0f} {profit:>+7.2f}% {mtf:<5} {momentum:<10} {clean:<7} {annotation:<30}")
    
    print()
    print("=" * 100)
    print("KEY FINDINGS")
    print("=" * 100)
    print()
    
    # Correlation analysis
    winners = df[df['actual_profit'] > 1]
    losers = df[df['actual_profit'] <= 1]
    
    print(f"WINNERS (profit > 1%):")
    print(f"  Count: {len(winners)}")
    print(f"  Avg Visual Pattern Score: {winners['visual_pattern_score'].mean():.1f}")
    print(f"  Avg MTF Alignment: {winners['mtf_alignment'].mean():.1f}/3")
    print(f"  Momentum Started: {winners['momentum_started'].sum()}/{len(winners)}")
    print(f"  Clean Pattern: {winners['clean_pattern'].sum()}/{len(winners)}")
    print(f"  Avg 3M Return: {winners['return_3m'].mean():+.1f}%")
    print()
    
    print(f"LOSERS (profit <= 1%):")
    print(f"  Count: {len(losers)}")
    print(f"  Avg Visual Pattern Score: {losers['visual_pattern_score'].mean():.1f}")
    print(f"  Avg MTF Alignment: {losers['mtf_alignment'].mean():.1f}/3")
    print(f"  Momentum Started: {losers['momentum_started'].sum()}/{len(losers)}")
    print(f"  Clean Pattern: {losers['clean_pattern'].sum()}/{len(losers)}")
    print(f"  Avg 3M Return: {losers['return_3m'].mean():+.1f}%")
    print()
    
    # Correlation
    corr_visual_profit = df['visual_pattern_score'].corr(df['actual_profit'])
    corr_mtf_profit = df['mtf_alignment'].corr(df['actual_profit'])
    corr_momentum_profit = df['momentum_started'].astype(int).corr(df['actual_profit'])
    
    print("CORRELATIONS:")
    print(f"  Visual Pattern Score vs Profit: {corr_visual_profit:+.3f}")
    print(f"  MTF Alignment vs Profit: {corr_mtf_profit:+.3f}")
    print(f"  Momentum Started vs Profit: {corr_momentum_profit:+.3f}")
    print()
    
    # Pattern type analysis
    print("=" * 100)
    print("PATTERN TYPE ANALYSIS")
    print("=" * 100)
    print()
    
    pattern_types = df.groupby('pattern_type').agg({
        'actual_profit': ['count', 'mean'],
        'visual_pattern_score': 'mean',
        'mtf_alignment': 'mean'
    }).round(2)
    
    print(pattern_types)
    print()
    
    print("=" * 100)
    print("VERDICT: WHAT MADE THE CHART PATTERNS WORK?")
    print("=" * 100)
    print()
    
    if corr_visual_profit > 0.5:
        print("VISUAL PATTERN QUALITY IS STRONGLY CORRELATED WITH PROFIT!")
        print()
        print("The charts worked because of:")
        print(f"  1. Multi-timeframe alignment: {corr_mtf_profit:+.3f} correlation")
        print(f"  2. Momentum already started: {corr_momentum_profit:+.3f} correlation")
        print(f"  3. Clean patterns (low volatility)")
        print(f"  4. Large measured moves (big targets)")
        print()
        print("RECOMMENDATION:")
        print("  Add VISUAL PATTERN QUALITY FILTER to scanner-v3:")
        print("    - Require 2/3 timeframes bullish (Daily + Weekly + Monthly)")
        print("    - Require momentum already started (3M return > 15%)")
        print("    - Require clean pattern (volatility < 40%)")
        print("    - Bonus for large measured moves (20%+ to 6M high)")
    else:
        print("VISUAL PATTERN QUALITY HAS WEAK/NO CORRELATION")
        print()
        print(f"Correlation: {corr_visual_profit:+.3f}")
        print()
        if corr_visual_profit < 0:
            print("NEGATIVE correlation means high visual scores predicted LOSSES!")
        else:
            print("Near-zero correlation means visual patterns don't predict profits")
        print()
        print("The charts worked due to LUCK, not visual pattern quality")
        print()
        print("RECOMMENDATION:")
        print("  Stick with scanner-v3 as-is")
        print("  Don't add visual pattern filters")
    
    # Save results
    output_file = f'results/chart_pattern_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False)
    print()
    print(f"Results saved to: {output_file}")

if __name__ == '__main__':
    main()
