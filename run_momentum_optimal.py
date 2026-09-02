"""Optimal momentum backtest: pullback 5-25%, vol 2-10x, no re-entry, on nifty500."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from backtest_momentum import (
    load_stocks, fetch_data, calc_atr,
    UPTREND_LOOKBACK, HIGH_LOOKBACK, VOLUME_LOOKBACK, ATR_PERIOD,
    ATR_MULT, MAX_STOP_PCT, T1_FRACTION, TIME_EXIT_DAYS,
    PULLBACK_MIN, PULLBACK_MAX, VOLUME_SURGE_MULT, MIN_DAY_GAIN,
)

VOL_SURGE_MAX = 10.0  # skip 10x+ blow-off tops


def detect_signals(df):
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
        if pd.isna(ret_6mo.iloc[i]) or ret_6mo.iloc[i] < 0.30: continue
        if pd.isna(pullback_pct.iloc[i]): continue
        pb = pullback_pct.iloc[i]
        if pb > -PULLBACK_MIN or pb < -PULLBACK_MAX: continue
        if pd.isna(vol_ratio.iloc[i]) or vol_ratio.iloc[i] < VOLUME_SURGE_MULT: continue
        if vol_ratio.iloc[i] > VOL_SURGE_MAX: continue
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
        distance = target_high - entry_price
        t2 = target_high
        risk = entry_price - stop_loss
        if risk <= 0: continue
        signals.append({
            "date": df.index[i], "entry": entry_price, "stop": stop_loss,
            "t2": t2, "pullback_pct": round(pb*100,2),
            "vol_ratio": round(float(vol_ratio.iloc[i]),2),
            "daily_gain": round(float(daily_ret.iloc[i])*100,2),
            "ret_6mo": round(float(ret_6mo.iloc[i])*100,2),
            "risk_pct": round(sl_pct*100,2), "rr_t2": round((t2-entry_price)/risk,2),
            "idx": i,
        })
    return signals


def simulate(df, signal):
    entry = signal["entry"]; stop = signal["stop"]; t2 = signal["t2"]
    start = signal["idx"]; end = min(start + TIME_EXIT_DAYS + 1, len(df))
    highs = df["High"].iloc[start+1:end]; lows = df["Low"].iloc[start+1:end]
    closes = df["Close"].iloc[start+1:end]
    if len(highs) == 0: return None
    for j in range(len(highs)):
        if float(lows.iloc[j]) <= stop:
            return {"entry": entry, "exit": stop, "pnl_pct": round((stop-entry)/entry*100,2),
                    "days_held": j+1, "status": "LOSS"}
        if float(highs.iloc[j]) >= t2:
            return {"entry": entry, "exit": t2, "pnl_pct": round((t2-entry)/entry*100,2),
                    "days_held": j+1, "status": "WIN_T2"}
    final = float(closes.iloc[-1])
    return {"entry": entry, "exit": final, "pnl_pct": round((final-entry)/entry*100,2),
            "days_held": len(highs), "status": "TIME_EXIT"}


def backtest(symbol, period="2y"):
    df = fetch_data(symbol, period)
    if df is None: return [], symbol
    signals = detect_signals(df)
    if not signals: return [], symbol
    trades = []; last_end = 0
    for sig in signals:
        if sig["idx"] < last_end: continue
        r = simulate(df, sig)
        if r:
            r["symbol"] = symbol; r["pullback_pct"] = sig["pullback_pct"]
            r["vol_ratio"] = sig["vol_ratio"]; r["daily_gain"] = sig["daily_gain"]
            r["ret_6mo"] = sig["ret_6mo"]; r["risk_pct"] = sig["risk_pct"]
            r["rr_t2"] = sig["rr_t2"]
            trades.append(r)
            last_end = sig["idx"] + r["days_held"] + 1
    return trades, symbol


def report(stocks, label, period="2y", workers=10):
    all_trades = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(backtest, s, period): s for s in stocks}
        for f in as_completed(futures):
            try:
                t, _ = f.result(); all_trades.extend(t)
            except: pass
    if not all_trades:
        print(f"\n  {label}: 0 trades"); return None
    df = pd.DataFrame(all_trades)
    total = len(df)
    wins = df[df["pnl_pct"] > 0]; losses = df[df["pnl_pct"] <= 0]
    wr = len(wins)/total*100
    aw = wins["pnl_pct"].mean() if len(wins)>0 else 0
    al = losses["pnl_pct"].mean() if len(losses)>0 else 0
    exp = df["pnl_pct"].mean()
    gp = wins["pnl_pct"].sum() if len(wins)>0 else 0
    gl = abs(losses["pnl_pct"].sum()) if len(losses)>0 else 0
    pf = gp/gl if gl>0 else 0
    running = df["pnl_pct"].cumsum()
    max_dd = (running - running.expanding().max()).min()
    avg_days = df["days_held"].mean()
    status = df["status"].value_counts().to_dict()

    print(f"\n  {'='*60}")
    print(f"  {label}")
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
    df["pb"] = pd.cut(df["pullback_pct"].abs(), bins=[0,10,15,20,25], labels=["5-10%","10-15%","15-20%","20-25%"])
    print(f"\n  By pullback depth:")
    for _, r in df.groupby("pb", observed=True).agg(t=("pnl_pct","count"), wr=("pnl_pct",lambda x:(x>0).mean()*100), avg=("pnl_pct","mean")).reset_index().iterrows():
        print(f"    {str(r['pb']):>10s}  {r['t']:>5d} trades  WR={r['wr']:.1f}%  avg={r['avg']:+.2f}%")

    # By volume
    df["vb"] = pd.cut(df["vol_ratio"], bins=[2,3,5,10], labels=["2-3x","3-5x","5-10x"])
    print(f"\n  By volume surge:")
    for _, r in df.groupby("vb", observed=True).agg(t=("pnl_pct","count"), wr=("pnl_pct",lambda x:(x>0).mean()*100), avg=("pnl_pct","mean")).reset_index().iterrows():
        print(f"    {str(r['vb']):>10s}  {r['t']:>5d} trades  WR={r['wr']:.1f}%  avg={r['avg']:+.2f}%")

    # By return
    df["rb"] = pd.cut(df["ret_6mo"], bins=[30,50,75,100,500], labels=["30-50%","50-75%","75-100%","100%+"])
    print(f"\n  By 6mo return:")
    for _, r in df.groupby("rb", observed=True).agg(t=("pnl_pct","count"), wr=("pnl_pct",lambda x:(x>0).mean()*100), avg=("pnl_pct","mean")).reset_index().iterrows():
        print(f"    {str(r['rb']):>10s}  {r['t']:>5d} trades  WR={r['wr']:.1f}%  avg={r['avg']:+.2f}%")

    # Monthly
    df["month"] = pd.to_datetime(df["entry_date"] if "entry_date" in df else df.get("date", pd.Timestamp.now())).dt.to_period("M") if "entry_date" in df else None

    # Comparison
    print(f"\n  COMPARISON vs v3.1:")
    print(f"    {'Metric':>15s}  {'Momentum':>10s}  {'v3.1':>10s}  {'Verdict':>10s}")
    print(f"    {'Trades':>15s}  {total:>10d}  {'3012':>10s}")
    print(f"    {'Win rate':>15s}  {wr:>9.1f}%  {'40.6%':>10s}  {'BETTER' if wr>40.6 else 'WORSE':>10s}")
    print(f"    {'Avg win':>15s}  {aw:>+9.2f}%  {'+7.6%':>10s}  {'BETTER' if aw>7.6 else 'WORSE':>10s}")
    print(f"    {'Avg loss':>15s}  {al:>+9.2f}%  {'-3.0%':>10s}  {'BETTER' if al>-3.0 else 'WORSE':>10s}")
    print(f"    {'Expectancy':>15s}  {exp:>+9.2f}%  {'+1.30%':>10s}  {'BETTER' if exp>1.30 else 'WORSE':>10s}")
    print(f"    {'Profit factor':>15s}  {pf:>10.2f}  {'1.73':>10s}  {'BETTER' if pf>1.73 else 'WORSE':>10s}")
    print(f"    {'Max drawdown':>15s}  {max_dd:>+9.2f}%  {'-60.1%':>10s}  {'BETTER' if max_dd>-60.1 else 'WORSE':>10s}")

    return df


print("=" * 70)
print("  OPTIMAL MOMENTUM BACKTEST (no re-entry, vol cap 10x)")
print("  Pullback 5-25%, Vol 2-10x, Uptrend 30%+, 2% gain, 2x ATR stop")
print("=" * 70)

nifty200 = load_stocks("nifty200.txt")
nifty500 = load_stocks("nifty500.txt")

df200 = report(nifty200, "NIFTY 200 (large caps, 2 years)")
df500 = report(nifty500, "NIFTY 500 (large+mid caps, 2 years)")

# Save
for df, name in [(df200, "nifty200"), (df500, "nifty500")]:
    if df is not None:
        out = os.path.join("results", f"momentum_optimal_{name}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv")
        df.to_csv(out, index=False)
        print(f"\n  Saved: {out}")
