#!/usr/bin/env python3
"""
Market Sentiment Analysis
Analyzes Nifty 50, sector rotation, breadth, and momentum conditions
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from utils.sector_rotation_v3 import get_sector_heat

def analyze_nifty():
    """Analyze Nifty 50 index"""
    print("\n" + "="*60)
    print("📊 NIFTY 50 INDEX ANALYSIS")
    print("="*60)
    
    # Download Nifty data
    nifty = yf.download('^NSEI', period='1y', progress=False)
    
    if nifty.empty:
        print("❌ Could not fetch Nifty data")
        return
    
    # Handle multi-index columns from yfinance
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.droplevel(1)
    
    current = float(nifty['Close'].iloc[-1])
    sma_50 = float(nifty['Close'].rolling(50).mean().iloc[-1])
    sma_200 = float(nifty['Close'].rolling(200).mean().iloc[-1])
    
    # Returns
    ret_1w = ((nifty['Close'].iloc[-1] / nifty['Close'].iloc[-5]) - 1) * 100
    ret_1m = ((nifty['Close'].iloc[-1] / nifty['Close'].iloc[-20]) - 1) * 100
    ret_3m = ((nifty['Close'].iloc[-1] / nifty['Close'].iloc[-60]) - 1) * 100
    ret_6m = ((nifty['Close'].iloc[-1] / nifty['Close'].iloc[-120]) - 1) * 100
    
    # Volatility
    volatility = nifty['Close'].pct_change().rolling(20).std().iloc[-1] * 100
    
    # Trend
    trend = "BULLISH 🟢" if current > sma_50 > sma_200 else \
            "BEARISH 🔴" if current < sma_50 < sma_200 else \
            "NEUTRAL 🟡"
    
    print(f"\n📈 Current Level: {current:,.2f}")
    print(f"📊 50-day SMA: {sma_50:,.2f} ({((current/sma_50-1)*100):+.2f}%)")
    print(f"📊 200-day SMA: {sma_200:,.2f} ({((current/sma_200-1)*100):+.2f}%)")
    print(f"\n🎯 Trend: {trend}")
    print(f"\n📅 Returns:")
    print(f"  1 Week:  {ret_1w:+.2f}%")
    print(f"  1 Month: {ret_1m:+.2f}%")
    print(f"  3 Month: {ret_3m:+.2f}%")
    print(f"  6 Month: {ret_6m:+.2f}%")
    print(f"\n📉 Volatility (20-day): {volatility:.2f}%")
    
    # Market regime
    if current > sma_50 and current > sma_200 and ret_1m > 0:
        regime = "STRONG UPTREND 🚀"
    elif current > sma_50 and current > sma_200:
        regime = "UPTREND 📈"
    elif current < sma_50 and current < sma_200 and ret_1m < 0:
        regime = "STRONG DOWNTREND 📉"
    elif current < sma_50 and current < sma_200:
        regime = "DOWNTREND 🔻"
    else:
        regime = "SIDEWAYS/CHOPPY 〰️"
    
    print(f"\n🎲 Market Regime: {regime}")
    
    return {
        'trend': trend,
        'regime': regime,
        'ret_1m': ret_1m,
        'ret_3m': ret_3m,
        'volatility': volatility
    }

def analyze_sectors():
    """Analyze sector performance"""
    print("\n" + "="*60)
    print("🏭 SECTOR ROTATION ANALYSIS")
    print("="*60)
    
    try:
        sectors = get_sector_heat(lookback_short=5, lookback_long=20)
        
        if not sectors:
            print("❌ Could not fetch sector data")
            return
        
        # Sort by short-term performance (5-day)
        sectors_sorted = sorted(sectors.items(), key=lambda x: x[1]['short'], reverse=True)
        
        print("\n🔥 TOP 5 SECTORS (Recent Performance):")
        for i, (sector, perf) in enumerate(sectors_sorted[:5], 1):
            print(f"  {i}. {sector:20s} Short: {perf['short']:+6.2f}% | Long: {perf['long']:+6.2f}%")
        
        print("\n❄️  BOTTOM 5 SECTORS (Recent Performance):")
        for i, (sector, perf) in enumerate(sectors_sorted[-5:], 1):
            print(f"  {i}. {sector:20s} Short: {perf['short']:+6.2f}% | Long: {perf['long']:+6.2f}%")
        
        # Count positive sectors
        positive_short = sum(1 for _, p in sectors.items() if p['short'] > 0)
        positive_long = sum(1 for _, p in sectors.items() if p['long'] > 0)
        total = len(sectors)
        
        print(f"\n📊 Sector Breadth:")
        print(f"  Short-term (5d): {positive_short}/{total} sectors positive ({positive_short/total*100:.1f}%)")
        print(f"  Long-term (20d): {positive_long}/{total} sectors positive ({positive_long/total*100:.1f}%)")
        
        # Rotation strength
        top_avg = sum(p['short'] for _, p in sectors_sorted[:5]) / 5
        bottom_avg = sum(p['short'] for _, p in sectors_sorted[-5:]) / 5
        rotation_strength = top_avg - bottom_avg
        
        print(f"\n🔄 Rotation Strength: {rotation_strength:.2f}%")
        if rotation_strength > 10:
            print("   → STRONG rotation (clear winners/losers)")
        elif rotation_strength > 5:
            print("   → MODERATE rotation")
        else:
            print("   → WEAK rotation (all sectors moving together)")
        
        return {
            'top_sectors': [s for s, _ in sectors_sorted[:5]],
            'bottom_sectors': [s for s, _ in sectors_sorted[-5:]],
            'breadth_1m': positive_short / total,
            'rotation_strength': rotation_strength
        }
        
    except Exception as e:
        print(f"❌ Error analyzing sectors: {e}")
        return None

def analyze_momentum():
    """Analyze market momentum conditions"""
    print("\n" + "="*60)
    print("⚡ MOMENTUM ANALYSIS")
    print("="*60)
    
    # Sample some high-momentum stocks
    momentum_stocks = [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS'
    ]
    
    strong_momentum = 0
    weak_momentum = 0
    
    for symbol in momentum_stocks:
        try:
            data = yf.download(symbol, period='3mo', progress=False)
            if not data.empty:
                ret_1m = ((data['Close'].iloc[-1] / data['Close'].iloc[-20]) - 1) * 100
                if ret_1m > 5:
                    strong_momentum += 1
                elif ret_1m < -5:
                    weak_momentum += 1
        except:
            continue
    
    total_checked = len(momentum_stocks)
    
    print(f"\n📊 Nifty 50 Momentum Sample ({total_checked} stocks):")
    print(f"  Strong momentum (>5% in 1M): {strong_momentum} ({strong_momentum/total_checked*100:.1f}%)")
    print(f"  Weak momentum (<-5% in 1M): {weak_momentum} ({weak_momentum/total_checked*100:.1f}%)")
    print(f"  Neutral: {total_checked - strong_momentum - weak_momentum}")
    
    if strong_momentum > total_checked * 0.6:
        momentum_env = "STRONG MOMENTUM 🚀"
    elif strong_momentum > total_checked * 0.4:
        momentum_env = "MODERATE MOMENTUM 📈"
    elif weak_momentum > total_checked * 0.6:
        momentum_env = "WEAK/BEARISH 📉"
    else:
        momentum_env = "CHOPPY/MIXED 〰️"
    
    print(f"\n⚡ Momentum Environment: {momentum_env}")
    
    return {
        'strong_pct': strong_momentum / total_checked,
        'weak_pct': weak_momentum / total_checked,
        'environment': momentum_env
    }

def provide_recommendations(nifty_data, sector_data, momentum_data):
    """Provide trading recommendations based on analysis"""
    print("\n" + "="*60)
    print("💡 TRADING RECOMMENDATIONS")
    print("="*60)
    
    # Overall market assessment
    if nifty_data['ret_1m'] < -5 and nifty_data['volatility'] > 1.5:
        market_condition = "BEARISH & VOLATILE"
        recommendation = "⚠️  DEFENSIVE MODE"
        advice = [
            "• Reduce position sizes",
            "• Tighten stop losses",
            "• Focus on quality stocks only",
            "• Consider cash/defensive sectors",
            "• Avoid aggressive breakout trades"
        ]
    elif nifty_data['ret_1m'] > 5 and momentum_data['strong_pct'] > 0.6:
        market_condition = "BULLISH & STRONG"
        recommendation = "🚀 AGGRESSIVE MODE"
        advice = [
            "• Increase position sizes",
            "• Focus on momentum leaders",
            f"• Trade top sectors: {', '.join(sector_data['top_sectors'][:3]) if sector_data else 'N/A'}",
            "• Look for breakout setups",
            "• Trail stops to lock profits"
        ]
    elif abs(nifty_data['ret_1m']) < 3 and nifty_data['volatility'] < 1.0:
        market_condition = "SIDEWAYS & QUIET"
        recommendation = "〰️  SELECTIVE MODE"
        advice = [
            "• Be very selective",
            "• Focus on individual stock setups",
            "• Avoid chasing breakouts",
            "• Consider range-bound strategies",
            "• Wait for clear trends to emerge"
        ]
    else:
        market_condition = "MIXED/TRANSITIONAL"
        recommendation = "⚖️  BALANCED MODE"
        advice = [
            "• Moderate position sizes",
            "• Stick to high-probability setups",
            "• Use standard stop losses",
            "• Monitor sector rotation closely",
            "• Be ready to adjust quickly"
        ]
    
    print(f"\n🎯 Market Condition: {market_condition}")
    print(f"📋 Recommendation: {recommendation}")
    print(f"\n📝 Action Items:")
    for item in advice:
        print(f"   {item}")
    
    # Why momentum might be weak
    if momentum_data['strong_pct'] < 0.3:
        print(f"\n❓ WHY IS MOMENTUM WEAK?")
        reasons = []
        
        if nifty_data['ret_1m'] < 0:
            reasons.append("• Market in downtrend (Nifty down in last month)")
        
        if nifty_data['volatility'] > 1.5:
            reasons.append("• High volatility creating uncertainty")
        
        if sector_data and sector_data['breadth_1m'] < 0.4:
            reasons.append(f"• Poor sector breadth ({sector_data['breadth_1m']*100:.0f}% sectors positive)")
        
        if sector_data and sector_data['rotation_strength'] < 5:
            reasons.append("• Weak sector rotation (no clear leaders)")
        
        if nifty_data['regime'] in ['SIDEWAYS/CHOPPY 〰️', 'DOWNTREND 🔻']:
            reasons.append(f"• Market regime: {nifty_data['regime']}")
        
        if not reasons:
            reasons.append("• Market consolidating after recent moves")
            reasons.append("• Waiting for catalysts (earnings, policy, global cues)")
        
        for reason in reasons:
            print(f"   {reason}")
        
        print(f"\n⏰ WHAT TO DO NOW?")
        print(f"   • Wait for confirmation of trend reversal")
        print(f"   • Focus on quality over quantity")
        print(f"   • Use scanner to find rare high-quality setups")
        print(f"   • Be patient - momentum will return")
        print(f"   • Consider paper trading to stay sharp")

def main():
    """Main analysis function"""
    print("\n" + "="*60)
    print("🔍 NSE MARKET SENTIMENT ANALYSIS")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)
    
    # Run all analyses
    nifty_data = analyze_nifty()
    sector_data = analyze_sectors()
    momentum_data = analyze_momentum()
    
    # Provide recommendations
    if nifty_data and momentum_data:
        provide_recommendations(nifty_data, sector_data, momentum_data)
    
    print("\n" + "="*60)
    print("✅ Analysis Complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
