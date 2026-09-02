"""Parameter sensitivity sweep for momentum strategy on nifty200."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from backtest_momentum import (
    load_stocks, fetch_data, calc_atr, simulate_trade,
    UPTREND_LOOKBACK, HIGH_LOOKBACK, VOLUME_LOOKBACK, ATR_PERIOD,
    ATR_MULT, MAX_STOP_PCT, T1_FRACTION, TIME_EXIT_DAYS,
    REENTRY_WINDOW, REENTRY_STOP_PCT
)

def detect_signals_with_params(df, uptrend_min, vol_mult, min_gain, pullback_min, pullback_max):
    close = df["Close"]; high = df["High"]; low = df["Low"]; volume = df["Volume"]
    ret_6mo = close.pct_change(periods=UPTREND_LOOKBACK)
    rolling_high = high.rolling(window=HIGH_LOOKBACK).max()
    pullback_pct = (close - rolling_high) / rolling_high
    avg_vol = volume.rolling(window=VOLUME_LOOKBACK).mean()
    vol_ratio = volume / avg_vol
    daily_ret = close.pct_change()
    atr = calc_atr(df, ATR_PERIOD)
    start_idx = max(UPTREND_LOOKBACK, HIGH_LOOKBACK + VOLUME_LOOKBACK + ATR_PERIOD)
    signals = []
    for i in range(start_idx, len(df) - 1):
        if pd.isna(ret_6mo.iloc[i]) or ret_6mo.iloc[i] < uptrend_min: continue
        if pd.isna(pullback_pct.iloc[i]): continue
        pb = pullback_pct.iloc[i]
        if pb > -pullback_min or pb < -pullback_max: continue
        if pd.isna(vol_ratio.iloc[i]) or vol_ratio.iloc[i] < vol_mult: continue
        if close.iloc[i] <= close.iloc[i-1]: continue
        if daily_ret.iloc[i] < min_gain: continue
        entry_price = float(close.iloc[i])
        target_high = float(rolling_high.iloc[i])
        atr_val = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else entry_price * 0.04
        sl_atr = entry_price - (ATR_MULT * atr_val)
        sl_pct = (entry_price - sl_atr) / entry_price
        if sl_pct > MAX_STOP_PCT:
            sl_atr = entry_price * (1 - MAX_STOP_PCT); sl_pct = MAX_STOP_PCT
        stop_loss = sl_atr
        distance_to_high = target_high - entry_price
        t1 = entry_price + (distance_to_high * T1_FRACTION)
        t2 = target_high
        risk = entry_price - stop_loss
        if risk <= 0: continue
        signals.append({
            "date": df.index[i], "entry": entry_price, "stop": stop_loss,
            "t1": t1, "t2": t2, "target_high": target_high,
            "pullback_pct": round(pb*100,2), "vol_ratio": round(float(vol_ratio.iloc[i]),2),
            "daily_gain": round(float(daily_ret.iloc[i])*100,2),
            "ret_6mo": round(float(ret_6mo.iloc[i])*100,2),
            "risk_pct": round(sl_pct*100,2), "rr_t2": round((t2-entry_price)/risk,2),
            "idx": i,
        })
    return signals

def backtest_stock_params(symbol, uptrend_min, vol_mult, min_gain, pb_min, pb_max, period="2y"):
    df = fetch_data(symbol, period)
    if df is None: return [], symbol
    signals = detect_signals_with_params(df, uptrend_min, vol_mult, min_gain, pb_min, pb_max)
    if not signals: return [], symbol
    trades = []
    last_end = 0
    for sig in signals:
        if sig["idx"] < last_end: continue
        result = simulate_trade(df, sig, use_t2=True)
        if result:
            result["symbol"] = symbol
            trades.append(result)
            last_end = sig["idx"] + result["days_held"] + 1
    return trades, symbol

def run_config(stocks, uptrend_min, vol_mult, min_gain, pb_min, pb_max, label):
    all_trades = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(backtest_stock_params, s, uptrend_min, vol_mult, min_gain, pb_min, pb_max): s for s in stocks}
        for f in as_completed(futures):
            try:
                trades, _ = f.result()
                all_trades.extend(trades)
            except: pass
    if not all_trades:
        print(f"  {label:30s}  0 trades")
        return
    df = pd.DataFrame(all_trades)
    total = len(df)
    wins = df[df["pnl_pct"] > 0]
    losses = df[df["pnl_pct"] <= 0]
    wr = len(wins)/total*100
    aw = wins["pnl_pct"].mean() if len(wins)>0 else 0
    al = losses["pnl_pct"].mean() if len(losses)>0 else 0
    exp = df["pnl_pct"].mean()
    gp = wins["pnl_pct"].sum() if len(wins)>0 else 0
    gl = abs(losses["pnl_pct"].sum()) if len(losses)>0 else 0
    pf = gp/gl if gl>0 else 0
    print(f"  {label:30s}  {total:>5d} trades  WR={wr:>5.1f}%  AW={aw:>+6.2f}%  AL={al:>+6.2f}%  EXP={exp:>+6.2f}%  PF={pf:>5.2f}")

stocks = load_stocks("nifty200.txt")
print("=" * 100)
print("  PARAMETER SENSITIVITY SWEEP (nifty200, 2 years)")
print("=" * 100)
print(f"  {'Config':>30s}  {'Trades':>7s}  {'WR':>7s}  {'AvgWin':>8s}  {'AvgLoss':>8s}  {'Exp':>7s}  {'PF':>5s}")
print("-" * 100)

# Baseline (current)
run_config(stocks, 0.30, 2.0, 0.02, 0.05, 0.25, "Baseline (30% ret, 2x vol, 2% gain)")

# Relax volume
run_config(stocks, 0.30, 1.5, 0.02, 0.05, 0.25, "Vol 1.5x (was 2x)")
run_config(stocks, 0.30, 2.5, 0.02, 0.05, 0.25, "Vol 2.5x (stricter)")
run_config(stocks, 0.30, 3.0, 0.02, 0.05, 0.25, "Vol 3.0x (strictest)")

# Relax uptrend
run_config(stocks, 0.20, 2.0, 0.02, 0.05, 0.25, "Uptrend 20% (was 30%)")
run_config(stocks, 0.40, 2.0, 0.02, 0.05, 0.25, "Uptrend 40% (stricter)")
run_config(stocks, 0.50, 2.0, 0.02, 0.05, 0.25, "Uptrend 50% (strictest)")

# Relax daily gain
run_config(stocks, 0.30, 2.0, 0.01, 0.05, 0.25, "Gain 1% (was 2%)")
run_config(stocks, 0.30, 2.0, 0.03, 0.05, 0.25, "Gain 3% (stricter)")
run_config(stocks, 0.30, 2.0, 0.05, 0.05, 0.25, "Gain 5% (strictest)")

# Pullback range
run_config(stocks, 0.30, 2.0, 0.02, 0.03, 0.25, "Pullback 3% min (was 5%)")
run_config(stocks, 0.30, 2.0, 0.02, 0.05, 0.15, "Pullback max 15% (was 25%)")
run_config(stocks, 0.30, 2.0, 0.02, 0.05, 0.20, "Pullback max 20% (was 25%)")

# Best combo (relaxed vol + stricter gain)
run_config(stocks, 0.30, 1.5, 0.03, 0.05, 0.20, "Combo: 1.5x vol, 3% gain, 20% pb")
run_config(stocks, 0.25, 1.5, 0.02, 0.05, 0.20, "Combo: 25% ret, 1.5x vol, 20% pb")
run_config(stocks, 0.30, 2.0, 0.03, 0.05, 0.20, "Combo: 2x vol, 3% gain, 20% pb")

print()
