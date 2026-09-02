"""Deep analysis of TECHM and VEDL — hold or exit decision."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
from data.loader import _fetch_nse

def analyse(sym, entry, stop, t1, t2, days_held, shares=None):
    print(f"\n{'='*70}")
    print(f"  {sym}  —  Hold or Exit?")
    print(f"{'='*70}")

    df = _fetch_nse(sym.replace('.NS',''), days=120)
    if df is None or df.empty:
        print("  No data")
        return

    cur   = float(df['Close'].iloc[-1])
    prev  = float(df['Close'].iloc[-2])
    high  = float(df['High'].iloc[-1])
    low   = float(df['Low'].iloc[-1])
    day_chg = (cur - prev) / prev * 100

    # Volume
    vol_today = float(df['Volume'].iloc[-1])
    vol_avg20 = float(df['Volume'].tail(21).iloc[:-1].mean())
    vol_ratio = vol_today / vol_avg20 if vol_avg20 > 0 else 1

    # ATR
    tr = np.maximum(df['High'] - df['Low'],
                    np.maximum((df['High'] - df['Close'].shift(1)).abs(),
                               (df['Low']  - df['Close'].shift(1)).abs()))
    atr = float(tr.rolling(14).mean().iloc[-1])

    # Moving averages
    sma20  = float(df['Close'].rolling(20).mean().iloc[-1])
    sma50  = float(df['Close'].rolling(50).mean().iloc[-1])
    ema9   = float(df['Close'].ewm(span=9).mean().iloc[-1])

    # RSI
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss
    rsi   = float((100 - 100 / (1 + rs)).iloc[-1])

    # Trend: last 10 closes
    closes_10 = df['Close'].tail(10).values
    trend_slope = np.polyfit(range(10), closes_10, 1)[0]
    trend = "UP" if trend_slope > 0 else "DOWN"

    # P&L
    pnl_pct  = (cur - entry) / entry * 100
    pnl_rs   = (cur - entry) * shares if shares else None
    to_stop  = (cur - stop)  / cur * 100
    to_t1    = (t1  - cur)   / cur * 100
    to_t2    = (t2  - cur)   / cur * 100
    rr_remain = to_t2 / to_stop if to_stop > 0 else 0

    # Support levels (recent lows)
    support1 = float(df['Low'].tail(10).min())
    support2 = float(df['Low'].tail(20).min())

    # Resistance (recent highs)
    resist1 = float(df['High'].tail(10).max())
    resist2 = float(df['High'].tail(20).max())

    print(f"  Entry:     Rs {entry:.2f}  |  Shares: {shares or '?'}")
    print(f"  CMP:       Rs {cur:.2f}  ({day_chg:+.2f}% today)")
    print(f"  P&L:       {pnl_pct:+.2f}%" + (f"  (Rs {pnl_rs:+,.0f})" if pnl_rs else ""))
    print()
    print(f"  Stop:      Rs {stop:.2f}  ({to_stop:+.1f}% away)")
    print(f"  T1:        Rs {t1:.2f}  ({to_t1:+.1f}% away)")
    print(f"  T2:        Rs {t2:.2f}  ({to_t2:+.1f}% away)")
    print(f"  R:R remain:{rr_remain:.2f}  (if T2 / if stop)")
    print()
    print(f"  RSI(14):   {rsi:.1f}  {'(overbought)' if rsi > 70 else '(neutral)' if rsi > 50 else '(weak)'}")
    print(f"  Trend:     {trend}  (slope {trend_slope:+.2f})")
    print(f"  EMA9:      {ema9:.2f}  {'(price above EMA9 - bullish)' if cur > ema9 else '(price below EMA9 - caution)'}")
    print(f"  SMA20:     {sma20:.2f}  {'(above - bullish)' if cur > sma20 else '(below - bearish)'}")
    print(f"  SMA50:     {sma50:.2f}  {'(above - bullish)' if cur > sma50 else '(below - bearish)'}")
    print(f"  ATR(14):   {atr:.2f}  ({atr/cur*100:.1f}% of price)")
    print(f"  Volume:    {vol_ratio:.1f}x avg  {'(surge!)' if vol_ratio > 1.5 else ''}")
    print()
    print(f"  Support1 (10d low):  {support1:.2f}  ({(cur-support1)/cur*100:.1f}% below CMP)")
    print(f"  Support2 (20d low):  {support2:.2f}  ({(cur-support2)/cur*100:.1f}% below CMP)")
    print(f"  Resist1  (10d high): {resist1:.2f}  ({(resist1-cur)/cur*100:.1f}% above CMP)")
    print(f"  Days held: {days_held}")

    # Decision logic
    print()
    print(f"  ANALYSIS:")
    signals_hold = []
    signals_exit = []

    # Trend
    if cur > sma20 > sma50:
        signals_hold.append("Price > SMA20 > SMA50 — uptrend intact")
    elif cur < sma20:
        signals_exit.append("Price below SMA20 — trend weakening")

    # RSI
    if rsi > 70:
        signals_exit.append(f"RSI {rsi:.0f} — overbought, potential pullback")
    elif rsi > 55:
        signals_hold.append(f"RSI {rsi:.0f} — momentum healthy, not overbought")
    elif rsi < 45:
        signals_exit.append(f"RSI {rsi:.0f} — momentum fading")

    # Stop distance
    if to_stop > 8:
        signals_hold.append(f"Stop {to_stop:.1f}% away — plenty of room")
    elif to_stop > 4:
        signals_hold.append(f"Stop {to_stop:.1f}% away — comfortable buffer")
    elif to_stop < 2:
        signals_exit.append(f"Only {to_stop:.1f}% to stop — dangerously close")

    # Upside remaining
    if to_t2 > 15:
        signals_hold.append(f"T2 is {to_t2:.1f}% away — significant upside left")
    elif to_t2 > 8:
        signals_hold.append(f"T2 is {to_t2:.1f}% away — good upside left")
    elif to_t2 < 5:
        signals_exit.append(f"T2 only {to_t2:.1f}% away — near target, consider taking profit")

    # T1 proximity
    if to_t1 < 3:
        signals_exit.append(f"T1 only {to_t1:.1f}% away — sell half at T1")
    elif to_t1 < 6:
        signals_hold.append(f"T1 {to_t1:.1f}% away — approaching first target")

    # Volume today
    if vol_ratio > 1.5:
        signals_hold.append(f"Volume {vol_ratio:.1f}x avg — accumulation signal")
    elif vol_ratio < 0.5:
        signals_exit.append(f"Volume only {vol_ratio:.1f}x — interest fading")

    # Trailing stop suggestion
    trailing_stop = max(support1, cur - 2 * atr)
    if trailing_stop > stop:
        signals_hold.append(f"Can trail stop up to {trailing_stop:.2f} (was {stop:.2f})")

    for s in signals_hold:
        print(f"    [HOLD] {s}")
    for s in signals_exit:
        print(f"    [CAUTION] {s}")

    # Final verdict
    hold_score = len(signals_hold)
    exit_score = len(signals_exit)
    print()
    if exit_score == 0 and hold_score >= 2:
        verdict = "HOLD — strong case, no red flags"
    elif exit_score >= 2:
        verdict = "CONSIDER EXITING — multiple caution signals"
    elif to_t1 < 3:
        verdict = "SELL HALF at T1 — approaching target, lock in partial profit"
    elif to_stop < 2:
        verdict = "TIGHT STOP — be ready to exit, move stop up"
    else:
        verdict = "HOLD with trailing stop — monitor closely"

    print(f"  VERDICT: {verdict}")
    if trailing_stop > stop:
        print(f"  Suggested trailing stop: Rs {trailing_stop:.2f}  (locks in profit)")

    return {
        'symbol': sym, 'cur': cur, 'pnl_pct': pnl_pct,
        'to_stop': to_stop, 'to_t1': to_t1, 'to_t2': to_t2,
        'rsi': rsi, 'trend': trend, 'verdict': verdict,
        'trailing_stop': trailing_stop,
    }

# TECHM — 20 shares, bought at 1589
r1 = analyse('TECHM.NS', entry=1589, stop=1530, t1=1687, t2=1750, days_held=14, shares=20)

# VEDL — from tracker (entry 259.35)
r2 = analyse('VEDL.NS', entry=259.35, stop=246.10, t1=330.10, t2=411.83, days_held=5, shares=None)

# Summary
print()
print("=" * 70)
print("  SUMMARY — Hold or Exit?")
print("=" * 70)
for r in [r1, r2]:
    if r:
        print(f"  {r['symbol']:14s}  P&L {r['pnl_pct']:+.1f}%  RSI {r['rsi']:.0f}  Trend {r['trend']}"
              f"  to_T1 {r['to_t1']:+.1f}%  to_T2 {r['to_t2']:+.1f}%  to_SL {r['to_stop']:+.1f}%")
        print(f"  {'':14s}  VERDICT: {r['verdict']}")
        print(f"  {'':14s}  Trail stop → Rs {r['trailing_stop']:.2f}")
        print()
