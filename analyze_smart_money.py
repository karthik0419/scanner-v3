"""
SMART MONEY ANALYSIS: Why did your chart picks work?

Hypothesis: The stocks that worked had INSTITUTIONAL BUYING (smart money)
that the simple momentum continuation strategy missed.

Smart Money Indicators:
1. Volume Profile: Unusual volume spikes (institutions accumulating)
2. Order Flow: Large block trades (hedge funds entering)
3. Price Action: Tight consolidation near highs (strong hands holding)
4. Relative Strength: Outperforming sector/market (institutional preference)
5. Liquidity: High volume stocks (institutions can enter/exit easily)
6. News/Events: Earnings, upgrades, sector rotation (institutional triggers)

Let's analyze the WINNERS vs LOSERS from your charts
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def analyze_smart_money_signals(symbol, analysis_date='2026-08-22'):
    """
    Analyze smart money indicators for a stock
    """
    try:
        # Download 1 year of data
        end_date = datetime.strptime(analysis_date, '%Y-%m-%d')
        start_date = end_date - timedelta(days=365)
        
        data = yf.download(symbol, start=start_date.strftime('%Y-%m-%d'), 
                          end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 50:
            return None
        
        # Calculate indicators
        data['SMA20'] = data['Close'].rolling(window=20).mean()
        data['SMA50'] = data['Close'].rolling(window=50).mean()
        data['SMA200'] = data['Close'].rolling(window=200).mean()
        data['AvgVolume20'] = data['Volume'].rolling(window=20).mean()
        data['AvgVolume50'] = data['Volume'].rolling(window=50).mean()
        
        # Get last 20 days
        recent = data.tail(20)
        last_day = data.iloc[-1]
        
        # 1. VOLUME ANALYSIS (Smart Money Accumulation)
        volume_surge_days = len(recent[recent['Volume'] > recent['AvgVolume50'] * 1.5])
        avg_volume_ratio = (recent['Volume'].mean() / recent['AvgVolume50'].mean())
        last_volume_ratio = last_day['Volume'] / last_day['AvgVolume50']
        
        # 2. PRICE ACTION (Tight Consolidation = Strong Hands)
        high_20d = recent['High'].max()
        low_20d = recent['Low'].min()
        consolidation_range = ((high_20d - low_20d) / low_20d) * 100
        
        # Distance from 20-day high
        distance_from_high = ((high_20d - last_day['Close']) / high_20d) * 100
        
        # 3. TREND STRENGTH (Institutional Preference)
        above_sma20 = last_day['Close'] > last_day['SMA20']
        above_sma50 = last_day['Close'] > last_day['SMA50']
        above_sma200 = last_day['Close'] > last_day['SMA200']
        
        sma_alignment = (last_day['SMA20'] > last_day['SMA50'] and 
                        last_day['SMA50'] > last_day['SMA200'])
        
        # 4. MOMENTUM (Recent Performance)
        return_1w = ((last_day['Close'] - data['Close'].iloc[-5]) / data['Close'].iloc[-5]) * 100 if len(data) >= 5 else 0
        return_1m = ((last_day['Close'] - data['Close'].iloc[-20]) / data['Close'].iloc[-20]) * 100 if len(data) >= 20 else 0
        return_3m = ((last_day['Close'] - data['Close'].iloc[-60]) / data['Close'].iloc[-60]) * 100 if len(data) >= 60 else 0
        
        # 5. VOLATILITY (Low volatility = Institutional Holding)
        returns = data['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized
        
        # 6. SMART MONEY SCORE (0-100)
        score = 0
        
        # Volume signals (30 points)
        if volume_surge_days >= 10:
            score += 15
        elif volume_surge_days >= 5:
            score += 10
        elif volume_surge_days >= 3:
            score += 5
        
        if avg_volume_ratio > 1.5:
            score += 10
        elif avg_volume_ratio > 1.2:
            score += 5
        
        if last_volume_ratio > 2.0:
            score += 5
        
        # Price action signals (25 points)
        if distance_from_high < 3:
            score += 15  # Very close to highs
        elif distance_from_high < 5:
            score += 10
        elif distance_from_high < 10:
            score += 5
        
        if consolidation_range < 10:
            score += 10  # Tight consolidation
        elif consolidation_range < 15:
            score += 5
        
        # Trend signals (25 points)
        if sma_alignment:
            score += 10
        if above_sma20:
            score += 5
        if above_sma50:
            score += 5
        if above_sma200:
            score += 5
        
        # Momentum signals (20 points)
        if return_1w > 5:
            score += 5
        if return_1m > 10:
            score += 10
        elif return_1m > 5:
            score += 5
        if return_3m > 20:
            score += 5
        
        return {
            'symbol': symbol,
            'close': last_day['Close'],
            'volume_surge_days': volume_surge_days,
            'avg_volume_ratio': avg_volume_ratio,
            'last_volume_ratio': last_volume_ratio,
            'consolidation_range': consolidation_range,
            'distance_from_high': distance_from_high,
            'above_sma20': above_sma20,
            'above_sma50': above_sma50,
            'above_sma200': above_sma200,
            'sma_alignment': sma_alignment,
            'return_1w': return_1w,
            'return_1m': return_1m,
            'return_3m': return_3m,
            'volatility': volatility,
            'smart_money_score': score
        }
    
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

def main():
    print("=" * 100)
    print("SMART MONEY ANALYSIS: Why Did Your Chart Picks Work?")
    print("=" * 100)
    print()
    
    # Your chart picks with actual 1-day performance
    stocks = {
        # WINNERS (made profit in 1 day)
        'CHENNPETRO.NS': {'profit': 33.75, 'scanner_status': 'WATCH', 'scanner_score': 52.3},
        'ANTHEM.NS': {'profit': 20.33, 'scanner_status': 'NEAR', 'scanner_score': 78.8},
        'VARROC.NS': {'profit': 19.99, 'scanner_status': 'NEAR', 'scanner_score': 56.8},
        'BRIGADE.NS': {'profit': 2.17, 'scanner_status': 'NEAR', 'scanner_score': 72.3},
        'ACE.NS': {'profit': 0.82, 'scanner_status': 'NEAR', 'scanner_score': 77.4},
        'CONCORDBIO.NS': {'profit': 0.36, 'scanner_status': 'NEAR', 'scanner_score': 54.2},
        'BALUFORGE.NS': {'profit': 0.00, 'scanner_status': 'NEAR', 'scanner_score': 61.3},
        
        # LOSERS (lost money in 1 day)
        'BALRAMCHIN.NS': {'profit': -0.78, 'scanner_status': 'NEAR', 'scanner_score': 56.7},
        'EPL.NS': {'profit': -0.00, 'scanner_status': 'NEAR', 'scanner_score': 86.5},
        'MANALIPETC.NS': {'profit': -0.00, 'scanner_status': 'WATCH', 'scanner_score': 71.7},
        'JTLIND.NS': {'profit': -0.00, 'scanner_status': 'REJECTED', 'scanner_score': 0},
    }
    
    print("Analyzing smart money indicators for all stocks...")
    print()
    
    results = []
    for symbol, info in stocks.items():
        analysis = analyze_smart_money_signals(symbol, '2026-08-22')
        if analysis:
            analysis['actual_profit'] = info['profit']
            analysis['scanner_status'] = info['scanner_status']
            analysis['scanner_score'] = info['scanner_score']
            results.append(analysis)
    
    df = pd.DataFrame(results)
    
    # Sort by smart money score
    df = df.sort_values('smart_money_score', ascending=False)
    
    print("=" * 100)
    print("SMART MONEY SCORES vs ACTUAL PERFORMANCE")
    print("=" * 100)
    print()
    
    print(f"{'Stock':<15} {'Smart$':<8} {'Profit':<8} {'Scanner':<10} {'Vol Surge':<10} {'Near High':<10} {'Trend':<8}")
    print("-" * 100)
    
    for _, row in df.iterrows():
        symbol_short = row['symbol'].replace('.NS', '')
        smart_score = row['smart_money_score']
        profit = row['actual_profit']
        scanner = f"{row['scanner_status'][:4]}/{row['scanner_score']:.0f}"
        vol_surge = f"{row['volume_surge_days']}/20d"
        near_high = f"{row['distance_from_high']:.1f}%"
        trend = "UP" if row['sma_alignment'] else "WEAK"
        
        print(f"{symbol_short:<15} {smart_score:<8.0f} {profit:>+7.2f}% {scanner:<10} {vol_surge:<10} {near_high:<10} {trend:<8}")
    
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
    print(f"  Avg Smart Money Score: {winners['smart_money_score'].mean():.1f}")
    print(f"  Avg Volume Surge Days: {winners['volume_surge_days'].mean():.1f}/20")
    print(f"  Avg Distance from High: {winners['distance_from_high'].mean():.1f}%")
    print(f"  Avg Scanner Score: {winners['scanner_score'].mean():.1f}")
    print()
    
    print(f"LOSERS (profit <= 1%):")
    print(f"  Count: {len(losers)}")
    print(f"  Avg Smart Money Score: {losers['smart_money_score'].mean():.1f}")
    print(f"  Avg Volume Surge Days: {losers['volume_surge_days'].mean():.1f}/20")
    print(f"  Avg Distance from High: {losers['distance_from_high'].mean():.1f}%")
    print(f"  Avg Scanner Score: {losers['scanner_score'].mean():.1f}")
    print()
    
    # Correlation
    corr_smart_profit = df['smart_money_score'].corr(df['actual_profit'])
    corr_scanner_profit = df['scanner_score'].corr(df['actual_profit'])
    
    print("CORRELATIONS:")
    print(f"  Smart Money Score vs Profit: {corr_smart_profit:+.3f}")
    print(f"  Scanner Score vs Profit: {corr_scanner_profit:+.3f}")
    print()
    
    # Top smart money picks
    print("=" * 100)
    print("TOP 5 SMART MONEY PICKS (High Score = Institutional Buying)")
    print("=" * 100)
    print()
    
    top5 = df.nlargest(5, 'smart_money_score')
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        symbol = row['symbol'].replace('.NS', '')
        score = row['smart_money_score']
        profit = row['actual_profit']
        vol_surge = row['volume_surge_days']
        near_high = row['distance_from_high']
        
        print(f"{i}. {symbol:<12} | Smart Money Score: {score:.0f}/100 | Actual Profit: {profit:+.2f}%")
        print(f"   Volume Surge: {vol_surge}/20 days | Distance from High: {near_high:.1f}%")
        print(f"   Trend: {'STRONG' if row['sma_alignment'] else 'WEAK'} | 1M Return: {row['return_1m']:+.1f}%")
        print()
    
    print("=" * 100)
    print("VERDICT: WHY DID YOUR PICKS WORK?")
    print("=" * 100)
    print()
    
    if corr_smart_profit > 0.5:
        print("SMART MONEY CORRELATION IS STRONG!")
        print()
        print("Your chart picks worked because they had INSTITUTIONAL BUYING:")
        print("  1. High volume surge days (smart money accumulating)")
        print("  2. Price near recent highs (strong hands holding)")
        print("  3. Strong trend alignment (institutions prefer uptrends)")
        print()
        print("RECOMMENDATION:")
        print("  Add SMART MONEY FILTER to scanner-v3:")
        print("    - Require 5+ volume surge days in last 20 days")
        print("    - Require price within 5% of 20-day high")
        print("    - Require SMA alignment (20 > 50 > 200)")
        print("    - Bonus points for stocks with Smart Money Score > 60")
    else:
        print("SMART MONEY CORRELATION IS WEAK")
        print()
        print("Your picks worked due to:")
        print("  1. Luck (small sample size)")
        print("  2. Market regime (bullish day)")
        print("  3. Survivorship bias (you only showed winners)")
        print()
        print("RECOMMENDATION:")
        print("  Stick with scanner-v3 as-is")
        print("  Don't add smart money filter (not predictive)")
    
    # Save results
    output_file = f'results/smart_money_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(output_file, index=False)
    print()
    print(f"Results saved to: {output_file}")

if __name__ == '__main__':
    main()
