"""Filtered momentum backtest with insights from full universe run."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from backtest_momentum import (
    load_stocks, fetch_data, calc_atr,
    UPTREND_LOOKBACK, HIGH_LOOKBACK, VOLUME_LOOKBACK, ATR_PERIOD,
    ATR_MULT, MAX_STOP_PCT, T1_FRACTION, TIME_EXIT_DAYS,
)

# FILTERED PARAMETERS based on full universe insights
PULLBACK_MAX = 0.15           # 15% max pullback (was 25%) — deeper = trend break
VOL_SURGE_MIN = 2.0           # 2x min volume
VOL_SURGE_MAX = 10.0          # skip 10x+ (blow-off tops, -0.36% expectancy)
UPTREND_MIN = 0.30            # 30% 6-month return
MIN_DAY_GAIN = 0.02           # 2% daily gain
DISABLE_REENTRY = True        # re-entry doesn't work for momentum (14.5% win vs 49.2% in v3.1)


def detect_signals_filtered(df):
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
        if pd.isna(ret_6mo.iloc[i]) or ret_6mo.iloc[i] < UPTREND_MIN: continue
        if pd.isna(pullback_pct.iloc[i]): continue
        pb = pullback_pct.iloc[i]
        if pb > -0.05 or pb < -PULLBACK_MAX: continue  # 5-15% pullback only
        if pd.isna(vol_ratio.iloc[i]) or vol_ratio.iloc[i] < VOL_SURGE_MIN: continue
        if vol_ratio.iloc[i] > VOL_SURGE_MAX: continue  # skip blow-off tops
        if close.iloc[i] <= close.iloc[i-1]: continue
        if daily_ret.iloc[i] < MIN_DAY_GAIN: continue
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


def simulate_no_reentry(df, signal):
    """Simulate trade without re-entry (re-entry doesn't work for momentum)."""
    entry = signal["entry"]; stop = signal["stop"]; t2 = signal["t2"]
    start_idx = signal["idx"]
    end_idx = min(start_idx + TIME_EXIT_DAYS + 1, len(df))
    highs = df["High"].iloc[start_idx+1:end_idx]
    lows = df["Low"].iloc[start_idx+1:end_idx]
    closes = df["Close"].iloc[start_idx+1:end_idx]
    if len(highs) == 0: return None
    for j in range(len(highs)):
        day_low = float(lows.iloc[j]); day_high = float(highs.iloc[j])
        days_held = j + 1
        if day_low <= stop:
            return {"entry": entry, "exit": stop, "pnl_pct": round((stop-entry)/entry*100,2),
                    "days_held": days_held, "status": "LOSS"}
        if day_high >= t2:
            return {"entry": entry, "exit": t2, "pnl_pct": round((t2-entry)/entry*100,2),
                    "days_held": days_held, "status": "WIN_T2"}
    final = float(closes.iloc[-1])
    return {"entry": entry, "exit": final, "pnl_pct": round((final-entry)/entry*100,2),
            "days_held": len(highs), "status": "TIME_EXIT"}


def backtest_stock_filtered(symbol, period="2y"):
    df = fetch_data(symbol, period)
    if df is None: return [], symbol
    signals = detect_signals_filtered(df)
    if not signals: return [], symbol
    trades = []; last_end = 0
    for sig in signals:
        if sig["idx"] < last_end: continue
        result = simulate_no_reentry(df, sig)
        if result:
            result["symbol"] = symbol
            result["pullback_pct"] = sig["pullback_pct"]
            result["vol_ratio"] = sig["vol_ratio"]
            result["daily_gain"] = sig["daily_gain"]
            result["ret_6mo"] = sig["ret_6mo"]
            result["risk_pct"] = sig["risk_pct"]
            result["rr_t2"] = sig["rr_t2"]
            trades.append(result)
            last_end = sig["idx"] + result["days_held"] + 1
    return trades, symbol


def run_and_report(stocks, label, period="2y", workers=10):
    all_trades = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(backtest_stock_filtered, s, period): s for s in stocks}
        for f in as_completed(futures):
            try:
                trades, _ = f.result()
                all_trades.extend(trades)
            except: pass
    if not all_trades:
        print(f"  {label}: 0 trades")
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
    running = df["pnl_pct"].cumsum()
    peak = running.expanding().max()
    max_dd = (running - peak).min()
    avg_days = df["days_held"].mean()
    status = df["status"].value_counts().to_dict()

    print(f"\n  {label}")
    print(f"  {'='*60}")
    print(f"  Total trades:     {total}")
    print(f"  Win rate:         {wr:.1f}%")
    print(f"  Avg win:          +{aw:.2f}%")
    print(f"  Avg loss:         {al:.2f}%")
    print(f"  Expectancy:       +{exp:.2f}%")
    print(f"  Profit factor:    {pf:.2f}")
    print(f"  Max drawdown:     {max_dd:.2f}%")
    print(f"  Avg days held:    {avg_days:.1f}")
    print(f"  Status: {status}")

    # By pullback
    df["pb"] = pd.cut(df["pullback_pct"].abs(), bins=[0,8,12,15], labels=["5-8%","8-12%","12-15%"])
    print(f"\n  By pullback:")
    for _, r in df.groupby("pb", observed=True).agg(t=("pnl_pct","count"), wr=("pnl_pct",lambda x:(x>0).mean()*100), avg=("pnl_pct","mean")).reset_index().iterrows():
        print(f"    {str(r['pb']):>10s}  {r['t']:>5d} trades  WR={r['wr']:.1f}%  avg={r['avg']:+.2f}%")

    # By volume
    df["vb"] = pd.cut(df["vol_ratio"], bins=[2,3,5,10], labels=["2-3x","3-5x","5-10x"])
    print(f"\n  By volume:")
    for _, r in df.groupby("vb", observed=True).agg(t=("pnl_pct","count"), wr=("pnl_pct",lambda x:(x>0).mean()*100), avg=("pnl_pct","mean")).reset_index().iterrows():
        print(f"    {str(r['vb']):>10s}  {r['t']:>5d} trades  WR={r['wr']:.1f}%  avg={r['avg']:+.2f}%")

    # By return
    df["rb"] = pd.cut(df["ret_6mo"], bins=[30,50,75,100,500], labels=["30-50%","50-75%","75-100%","100%+"])
    print(f"\n  By 6mo return:")
    for _, r in df.groupby("rb", observed=True).agg(t=("pnl_pct","count"), wr=("pnl_pct",lambda x:(x>0).mean()*100), avg=("pnl_pct","mean")).reset_index().iterrows():
        print(f"    {str(r['rb']):>10s}  {r['t']:>5d} trades  WR={r['wr']:.1f}%  avg={r['avg']:+.2f}%")

    # Comparison
    print(f"\n  COMPARISON vs v3.1:")
    print(f"    {'Metric':>15s}  {'Filtered':>10s}  {'v3.1':>10s}  {'Verdict':>10s}")
    print(f"    {'Trades':>15s}  {total:>10d}  {'3012':>10s}")
    print(f"    {'Win rate':>15s}  {wr:>9.1f}%  {'40.6%':>10s}  {'BETTER' if wr>40.6 else 'WORSE':>10s}")
    print(f"    {'Avg win':>15s}  {aw:>+9.2f}%  {'+7.6%':>10s}  {'BETTER' if aw>7.6 else 'WORSE':>10s}")
    print(f"    {'Avg loss':>15s}  {al:>+9.2f}%  {'-3.0%':>10s}  {'BETTER' if al>-3.0 else 'WORSE':>10s}")
    print(f"    {'Expectancy':>15s}  {exp:>+9.2f}%  {'+1.30%':>10s}  {'BETTER' if exp>1.30 else 'WORSE':>10s}")
    print(f"    {'Profit factor':>15s}  {pf:>10.2f}  {'1.73':>10s}  {'BETTER' if pf>1.73 else 'WORSE':>10s}")
    print(f"    {'Max drawdown':>15s}  {max_dd:>+9.2f}%  {'-60.1%':>10s}  {'BETTER' if max_dd>-60.1 else 'WORSE':>10s}")

    return df


# Run on both universes
print("=" * 70)
print("  FILTERED MOMENTUM BACKTEST")
print("  Filters: Pullback 5-15%, Vol 2-10x, No re-entry, 8% stop cap")
print("=" * 70)

nifty200 = load_stocks("nifty200.txt")
df200 = run_and_report(nifty200, "NIFTY 200 (large caps)")

# Full NSE EQ
from data.nse_eq import fetch_nse_eq_universe
full = fetch_nse_eq_universe()
df_full = run_and_report(full, "FULL NSE EQ (all caps)")

# Save
if df_full is not None:
    out = os.path.join("results", f"momentum_filtered_full_{pd.Timestamp.now().strftime('%Y%m%d')}.csv")
    df_full.to_csv(out, index=False)
    print(f"\n  Saved: {out}")
