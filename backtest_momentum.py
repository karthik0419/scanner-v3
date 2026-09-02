"""
Momentum Continuation Backtest
===============================
Strategy: Catch strong-uptrend stocks that pulled back from highs,
          then bouncing with volume surge.

The VINDHYATEL pattern (03 Aug 2026):
  - Stock up 84% in 6mo (strong uptrend)
  - Pulled back 28% from 50-day high (2477 -> 1789)
  - Bounced +8.85% with 3.4x volume
  - Question: does entering on the bounce reach the previous high?

ENTRY RULES (all must be true):
  1. Uptrend: 6-month return > 30%
  2. Pullback: current price is 5-25% below 50-day high
  3. Volume surge: today's volume > 2x 20-day avg volume
  4. Up day: today's close > yesterday's close
  5. Meaningful bounce: today's gain > 2%

EXIT RULES:
  - SL: 2x ATR below entry, capped at 8% max
  - T1: 50% of distance from entry to 50-day high
  - T2: full distance to 50-day high
  - Time exit: 30 trading days
  - Re-entry: if SL hit but stock recovers above entry within 15 days,
    re-enter with 2% tight stop

Usage:
  python backtest_momentum.py                    # nifty200, 2 years
  python backtest_momentum.py --stocks backbone50.txt --years 3
  python backtest_momentum.py --workers 8        # parallel
"""

import argparse
import os
import sys
import warnings
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ============================================================
# STRATEGY PARAMETERS
# ============================================================
UPTREND_LOOKBACK = 126        # ~6 months trading days
UPTREND_MIN_RETURN = 0.30     # 30% minimum 6-month return
PULLBACK_MIN = 0.05           # 5% below 50-day high
PULLBACK_MAX = 0.25           # 25% below 50-day high (too deep = trend break)
HIGH_LOOKBACK = 50            # 50-day high as the target resistance
VOLUME_LOOKBACK = 20          # 20-day avg volume
VOLUME_SURGE_MULT = 2.0       # 2x volume surge
MIN_DAY_GAIN = 0.02           # 2% minimum daily gain
ATR_PERIOD = 14
ATR_MULT = 2.0                # 2x ATR stop (consistent with v3.1)
MAX_STOP_PCT = 0.08           # 8% max stop cap (consistent with v3.1)
T1_FRACTION = 0.50            # T1 = 50% of distance to 50-day high
TIME_EXIT_DAYS = 30           # 30 trading days max hold
REENTRY_WINDOW = 15           # 15 days to check for re-entry
REENTRY_STOP_PCT = 0.02       # 2% tight stop on re-entry


def load_stocks(filepath):
    stocks = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                stocks.append(line if line.endswith(".NS") else line + ".NS")
    return stocks


def fetch_data(symbol, period="2y"):
    try:
        t = yf.Ticker(symbol)
        df = t.history(period=period)
        if df is None or len(df) < 200:
            return None
        df = df.dropna()
        return df
    except Exception:
        return None


def calc_atr(df, period=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def detect_momentum_signals(df):
    """Find all dates where momentum continuation signal fires."""
    signals = []

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # 6-month return (126 trading days)
    ret_6mo = close.pct_change(periods=UPTREND_LOOKBACK)

    # 50-day rolling high
    rolling_high = high.rolling(window=HIGH_LOOKBACK).max()

    # Pullback from 50-day high
    pullback_pct = (close - rolling_high) / rolling_high

    # 20-day average volume
    avg_vol = volume.rolling(window=VOLUME_LOOKBACK).mean()

    # Volume ratio
    vol_ratio = volume / avg_vol

    # Daily return
    daily_ret = close.pct_change()

    # ATR
    atr = calc_atr(df, ATR_PERIOD)

    # Iterate from the first valid index
    start_idx = max(UPTREND_LOOKBACK, HIGH_LOOKBACK + VOLUME_LOOKBACK + ATR_PERIOD)

    for i in range(start_idx, len(df) - 1):  # -1 because we need next day for entry
        # Rule 1: Uptrend — 6-month return > 30%
        if pd.isna(ret_6mo.iloc[i]) or ret_6mo.iloc[i] < UPTREND_MIN_RETURN:
            continue

        # Rule 2: Pullback — 5% to 25% below 50-day high
        if pd.isna(pullback_pct.iloc[i]):
            continue
        pb = pullback_pct.iloc[i]
        if pb > -PULLBACK_MIN or pb < -PULLBACK_MAX:
            continue

        # Rule 3: Volume surge — > 2x 20-day average
        if pd.isna(vol_ratio.iloc[i]) or vol_ratio.iloc[i] < VOLUME_SURGE_MULT:
            continue

        # Rule 4: Up day — close > prev close
        if close.iloc[i] <= close.iloc[i - 1]:
            continue

        # Rule 5: Meaningful bounce — daily gain > 2%
        if daily_ret.iloc[i] < MIN_DAY_GAIN:
            continue

        # --- Signal fires ---
        entry_price = float(close.iloc[i])
        signal_date = df.index[i]

        # 50-day high (the target resistance)
        target_high = float(rolling_high.iloc[i])

        # ATR-based stop loss
        atr_val = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else entry_price * 0.04
        sl_atr = entry_price - (ATR_MULT * atr_val)
        sl_pct = (entry_price - sl_atr) / entry_price

        # Cap stop at 8%
        if sl_pct > MAX_STOP_PCT:
            sl_atr = entry_price * (1 - MAX_STOP_PCT)
            sl_pct = MAX_STOP_PCT

        stop_loss = sl_atr

        # Targets
        distance_to_high = target_high - entry_price
        t1 = entry_price + (distance_to_high * T1_FRACTION)
        t2 = target_high  # full distance to 50-day high

        # R:R
        risk = entry_price - stop_loss
        if risk <= 0:
            continue

        rr_t1 = (t1 - entry_price) / risk
        rr_t2 = (t2 - entry_price) / risk

        signals.append({
            "date": signal_date,
            "entry": entry_price,
            "stop": stop_loss,
            "t1": t1,
            "t2": t2,
            "target_high": target_high,
            "pullback_pct": round(pb * 100, 2),
            "vol_ratio": round(float(vol_ratio.iloc[i]), 2),
            "daily_gain": round(float(daily_ret.iloc[i]) * 100, 2),
            "ret_6mo": round(float(ret_6mo.iloc[i]) * 100, 2),
            "risk_pct": round(sl_pct * 100, 2),
            "rr_t1": round(rr_t1, 2),
            "rr_t2": round(rr_t2, 2),
            "idx": i,
        })

    return signals


def simulate_trade(df, signal, use_t2=True):
    """Simulate a single trade from signal. Returns trade result dict."""
    entry = signal["entry"]
    stop = signal["stop"]
    t1 = signal["t1"]
    t2 = signal["t2"]
    start_idx = signal["idx"]

    # Look forward up to TIME_EXIT_DAYS
    end_idx = min(start_idx + TIME_EXIT_DAYS + 1, len(df))

    highs = df["High"].iloc[start_idx + 1 : end_idx]
    lows = df["Low"].iloc[start_idx + 1 : end_idx]
    closes = df["Close"].iloc[start_idx + 1 : end_idx]

    if len(highs) == 0:
        return None

    target = t2 if use_t2 else t1

    # Check day by day: SL first (conservative — if both hit on same day, SL wins)
    for j in range(len(highs)):
        day_low = float(lows.iloc[j])
        day_high = float(highs.iloc[j])
        day_close = float(closes.iloc[j])
        days_held = j + 1

        # Stop loss hit
        if day_low <= stop:
            # Check if same day also hit target (rare) — assume SL first
            pnl_pct = (stop - entry) / entry * 100

            # Check for re-entry within REENTRY_WINDOW
            reentry_result = check_reentry(df, start_idx + 1 + j, entry, signal)
            if reentry_result:
                return {
                    "entry_date": signal["date"],
                    "entry": entry,
                    "exit": reentry_result["exit"],
                    "pnl_pct": reentry_result["pnl_pct"],
                    "days_held": reentry_result["days_held"],
                    "status": "RE_ENTERED_" + reentry_result["status"],
                    "stop": stop,
                    "t1": t1,
                    "t2": t2,
                }
            return {
                "entry_date": signal["date"],
                "entry": entry,
                "exit": stop,
                "pnl_pct": round(pnl_pct, 2),
                "days_held": days_held,
                "status": "LOSS",
                "stop": stop,
                "t1": t1,
                "t2": t2,
            }

        # Target hit
        if day_high >= target:
            pnl_pct = (target - entry) / entry * 100
            status = "WIN_T2" if use_t2 else "WIN_T1"
            return {
                "entry_date": signal["date"],
                "entry": entry,
                "exit": target,
                "pnl_pct": round(pnl_pct, 2),
                "days_held": days_held,
                "status": status,
                "stop": stop,
                "t1": t1,
                "t2": t2,
            }

    # Time exit — close at last day's close
    final_close = float(closes.iloc[-1])
    pnl_pct = (final_close - entry) / entry * 100
    return {
        "entry_date": signal["date"],
        "entry": entry,
        "exit": final_close,
        "pnl_pct": round(pnl_pct, 2),
        "days_held": len(highs),
        "status": "TIME_EXIT",
        "stop": stop,
        "t1": t1,
        "t2": t2,
    }


def check_reentry(df, sl_idx, original_entry, signal):
    """After SL hit, check if stock recovers above entry within REENTRY_WINDOW.
    If yes, re-enter with tight 2% stop. Simulate to T1 or T2 or new SL."""
    entry = original_entry
    reentry_stop = entry * (1 - REENTRY_STOP_PCT)
    t1 = signal["t1"]
    t2 = signal["t2"]
    target = t2  # aim for T2 on re-entry

    end_idx = min(sl_idx + REENTRY_WINDOW + 1, len(df))

    for j in range(sl_idx, end_idx):
        day_high = float(df["High"].iloc[j])
        day_low = float(df["Low"].iloc[j])
        day_close = float(df["Close"].iloc[j])

        # Stock recovered above original entry
        if day_high >= entry:
            # Re-entered at entry price
            # Now simulate from this point
            reentry_start = j
            reentry_end = min(reentry_start + TIME_EXIT_DAYS, len(df))

            for k in range(reentry_start + 1, reentry_end):
                d_low = float(df["Low"].iloc[k])
                d_high = float(df["High"].iloc[k])
                d_close = float(df["Close"].iloc[k])
                days = (k - sl_idx) + 1

                if d_low <= reentry_stop:
                    pnl = (reentry_stop - entry) / entry * 100
                    return {
                        "exit": reentry_stop,
                        "pnl_pct": round(pnl, 2),
                        "days_held": days,
                        "status": "LOSS",
                    }

                if d_high >= target:
                    pnl = (target - entry) / entry * 100
                    return {
                        "exit": target,
                        "pnl_pct": round(pnl, 2),
                        "days_held": days,
                        "status": "WIN",
                    }

            # Time exit on re-entry
            final = float(df["Close"].iloc[reentry_end - 1])
            pnl = (final - entry) / entry * 100
            return {
                "exit": final,
                "pnl_pct": round(pnl, 2),
                "days_held": reentry_end - sl_idx,
                "status": "TIME_EXIT",
            }

    return None


def backtest_stock(symbol, period="2y"):
    """Run momentum backtest on a single stock. Returns list of trade dicts."""
    df = fetch_data(symbol, period)
    if df is None:
        return [], symbol

    signals = detect_momentum_signals(df)
    if not signals:
        return [], symbol

    trades = []
    last_trade_end_idx = 0

    for sig in signals:
        # Avoid overlapping trades — skip if previous trade is still active
        if sig["idx"] < last_trade_end_idx:
            continue

        result = simulate_trade(df, sig, use_t2=True)
        if result:
            result["symbol"] = symbol
            result["pullback_pct"] = sig["pullback_pct"]
            result["vol_ratio"] = sig["vol_ratio"]
            result["daily_gain"] = sig["daily_gain"]
            result["ret_6mo"] = sig["ret_6mo"]
            result["risk_pct"] = sig["risk_pct"]
            result["rr_t2"] = sig["rr_t2"]
            trades.append(result)
            last_trade_end_idx = sig["idx"] + result["days_held"] + 1

    return trades, symbol


def analyze_results(trades):
    """Analyze backtest results and return summary stats."""
    if not trades:
        return None

    df = pd.DataFrame(trades)

    total = len(df)
    wins = df[df["pnl_pct"] > 0]
    losses = df[df["pnl_pct"] <= 0]

    win_rate = len(wins) / total * 100 if total > 0 else 0
    avg_win = wins["pnl_pct"].mean() if len(wins) > 0 else 0
    avg_loss = losses["pnl_pct"].mean() if len(losses) > 0 else 0
    expectancy = df["pnl_pct"].mean()
    total_return = df["pnl_pct"].sum()

    # Profit factor
    gross_profit = wins["pnl_pct"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl_pct"].sum()) if len(losses) > 0 else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown (simplified — running sum of pnl)
    running = df["pnl_pct"].cumsum()
    peak = running.expanding().max()
    dd = running - peak
    max_dd = dd.min() if len(dd) > 0 else 0

    # Status breakdown
    status_counts = df["status"].value_counts().to_dict()

    # By pullback depth
    df["pb_bucket"] = pd.cut(
        df["pullback_pct"].abs(),
        bins=[0, 10, 15, 20, 25],
        labels=["5-10%", "10-15%", "15-20%", "20-25%"],
    )
    by_pullback = df.groupby("pb_bucket", observed=True).agg(
        trades=("pnl_pct", "count"),
        win_rate=("pnl_pct", lambda x: (x > 0).mean() * 100),
        avg_pnl=("pnl_pct", "mean"),
    ).reset_index()

    # By volume ratio
    df["vol_bucket"] = pd.cut(
        df["vol_ratio"],
        bins=[2, 3, 5, 10, 100],
        labels=["2-3x", "3-5x", "5-10x", "10x+"],
    )
    by_volume = df.groupby("vol_bucket", observed=True).agg(
        trades=("pnl_pct", "count"),
        win_rate=("pnl_pct", lambda x: (x > 0).mean() * 100),
        avg_pnl=("pnl_pct", "mean"),
    ).reset_index()

    # By 6-month return
    df["ret_bucket"] = pd.cut(
        df["ret_6mo"],
        bins=[30, 50, 75, 100, 500],
        labels=["30-50%", "50-75%", "75-100%", "100%+"],
    )
    by_return = df.groupby("ret_bucket", observed=True).agg(
        trades=("pnl_pct", "count"),
        win_rate=("pnl_pct", lambda x: (x > 0).mean() * 100),
        avg_pnl=("pnl_pct", "mean"),
    ).reset_index()

    # Avg days held
    avg_days = df["days_held"].mean()

    # Re-entry stats
    reentered = df[df["status"].str.startswith("RE_ENTERED")]
    re_stats = None
    if len(reentered) > 0:
        re_wins = reentered[reentered["pnl_pct"] > 0]
        re_stats = {
            "trades": len(reentered),
            "win_rate": len(re_wins) / len(reentered) * 100,
            "avg_pnl": reentered["pnl_pct"].mean(),
        }

    return {
        "total_trades": total,
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "profit_factor": round(pf, 2),
        "total_return": round(total_return, 2),
        "max_dd": round(max_dd, 2),
        "avg_days_held": round(avg_days, 1),
        "status_counts": status_counts,
        "by_pullback": by_pullback.to_dict("records"),
        "by_volume": by_volume.to_dict("records"),
        "by_return": by_return.to_dict("records"),
        "reentry_stats": re_stats,
        "trades_df": df,
    }


def main():
    parser = argparse.ArgumentParser(description="Momentum Continuation Backtest")
    parser.add_argument("--stocks", default="nifty200.txt", help="Stock universe file")
    parser.add_argument("--years", type=int, default=2, help="Years of history")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    parser.add_argument("--save", action="store_true", help="Save trades to CSV")
    args = parser.parse_args()

    stocks_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.stocks)
    stocks = load_stocks(stocks_file)
    period = f"{args.years}y"

    print("=" * 70)
    print(f"  MOMENTUM CONTINUATION BACKTEST")
    print(f"  Universe: {args.stocks} ({len(stocks)} stocks)")
    print(f"  Period: {args.years} years")
    print(f"  Strategy: Uptrend > 30% 6mo, Pullback 5-25%, Vol surge 2x+, Gain > 2%")
    print(f"  Exit: 2x ATR stop (8% cap), T2 = 50-day high, 30-day time exit")
    print(f"  Re-entry: recover above entry in 15 days, 2% tight stop")
    print("=" * 70)
    print()

    all_trades = []
    completed = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(backtest_stock, s, period): s for s in stocks}

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                trades, sym = future.result()
                completed += 1
                if trades:
                    all_trades.extend(trades)
                    print(f"  [{completed}/{len(stocks)}] {sym}: {len(trades)} trades")
                else:
                    pass  # silent for no-signal stocks
            except Exception as e:
                errors += 1
                print(f"  ERROR {symbol}: {e}")

    print()
    print(f"  Scanned: {completed} stocks, Errors: {errors}")
    print(f"  Total signals/trades: {len(all_trades)}")
    print()

    if not all_trades:
        print("  No momentum signals found in the universe. Try relaxing parameters.")
        return

    results = analyze_results(all_trades)
    if not results:
        print("  Analysis failed.")
        return

    # Print summary
    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    print(f"  Total trades:       {results['total_trades']}")
    print(f"  Win rate:           {results['win_rate']}%")
    print(f"  Avg win:            +{results['avg_win']}%")
    print(f"  Avg loss:           {results['avg_loss']}%")
    print(f"  Expectancy/trade:   {results['expectancy']}%")
    print(f"  Profit factor:      {results['profit_factor']}")
    print(f"  Total return:       {results['total_return']}%")
    print(f"  Max drawdown:       {results['max_dd']}%")
    print(f"  Avg days held:      {results['avg_days_held']}")
    print()

    print("  Status breakdown:")
    for status, count in sorted(results["status_counts"].items()):
        print(f"    {status:20s}: {count}")
    print()

    print("  By pullback depth:")
    print(f"    {'Pullback':>12s}  {'Trades':>7s}  {'Win%':>7s}  {'Avg P&L':>8s}")
    for r in results["by_pullback"]:
        print(f"    {str(r['pb_bucket']):>12s}  {r['trades']:>7d}  {r['win_rate']:>6.1f}%  {r['avg_pnl']:>+7.2f}%")
    print()

    print("  By volume surge:")
    print(f"    {'Vol Ratio':>12s}  {'Trades':>7s}  {'Win%':>7s}  {'Avg P&L':>8s}")
    for r in results["by_volume"]:
        print(f"    {str(r['vol_bucket']):>12s}  {r['trades']:>7d}  {r['win_rate']:>6.1f}%  {r['avg_pnl']:>+7.2f}%")
    print()

    print("  By 6-month return:")
    print(f"    {'6mo Return':>12s}  {'Trades':>7s}  {'Win%':>7s}  {'Avg P&L':>8s}")
    for r in results["by_return"]:
        print(f"    {str(r['ret_bucket']):>12s}  {r['trades']:>7d}  {r['win_rate']:>6.1f}%  {r['avg_pnl']:>+7.2f}%")
    print()

    if results["reentry_stats"]:
        re = results["reentry_stats"]
        print(f"  Re-entry stats: {re['trades']} trades, {re['win_rate']:.1f}% win, {re['avg_pnl']:+.2f}% avg")
    else:
        print("  Re-entry stats: no re-entries triggered")
    print()

    # Per-stock breakdown (top performers)
    df = results["trades_df"]
    stock_stats = df.groupby("symbol").agg(
        trades=("pnl_pct", "count"),
        win_rate=("pnl_pct", lambda x: (x > 0).mean() * 100),
        avg_pnl=("pnl_pct", "mean"),
        total_pnl=("pnl_pct", "sum"),
    ).reset_index().sort_values("total_pnl", ascending=False)

    print("  Top 10 stocks by total P&L:")
    print(f"    {'Symbol':>18s}  {'Trades':>7s}  {'Win%':>7s}  {'Avg P&L':>8s}  {'Total':>8s}")
    for _, r in stock_stats.head(10).iterrows():
        print(f"    {r['symbol']:>18s}  {r['trades']:>7d}  {r['win_rate']:>6.1f}%  {r['avg_pnl']:>+7.2f}%  {r['total_pnl']:>+7.2f}%")
    print()

    print("  Worst 5 stocks by total P&L:")
    for _, r in stock_stats.tail(5).iterrows():
        print(f"    {r['symbol']:>18s}  {r['trades']:>7d}  {r['win_rate']:>6.1f}%  {r['avg_pnl']:>+7.2f}%  {r['total_pnl']:>+7.2f}%")
    print()

    # Monthly distribution
    df["month"] = pd.to_datetime(df["entry_date"]).dt.to_period("M")
    monthly = df.groupby("month").agg(
        trades=("pnl_pct", "count"),
        win_rate=("pnl_pct", lambda x: (x > 0).mean() * 100),
        avg_pnl=("pnl_pct", "mean"),
    ).reset_index()

    print("  Monthly performance (last 12 months):")
    print(f"    {'Month':>10s}  {'Trades':>7s}  {'Win%':>7s}  {'Avg P&L':>8s}")
    for _, r in monthly.tail(12).iterrows():
        print(f"    {str(r['month']):>10s}  {r['trades']:>7d}  {r['win_rate']:>6.1f}%  {r['avg_pnl']:>+7.2f}%")
    print()

    # Comparison with v3.1
    print("=" * 70)
    print("  COMPARISON: Momentum vs v3.1 (pattern-based)")
    print("=" * 70)
    print(f"  {'Metric':>20s}  {'Momentum':>12s}  {'v3.1':>12s}")
    print(f"  {'Trades':>20s}  {results['total_trades']:>12d}  {'3012':>12s}")
    print(f"  {'Win rate':>20s}  {results['win_rate']:>11.1f}%  {'40.6%':>12s}")
    print(f"  {'Avg win':>20s}  {results['avg_win']:>+11.2f}%  {'+7.6%':>12s}")
    print(f"  {'Avg loss':>20s}  {results['avg_loss']:>+11.2f}%  {'-3.0%':>12s}")
    print(f"  {'Expectancy':>20s}  {results['expectancy']:>+11.2f}%  {'+1.30%':>12s}")
    print(f"  {'Profit factor':>20s}  {results['profit_factor']:>12.2f}  {'1.73':>12s}")
    print(f"  {'Max drawdown':>20s}  {results['max_dd']:>+11.2f}%  {'-60.1%':>12s}")
    print()

    # Save trades
    if args.save:
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "results",
            f"momentum_backtest_{datetime.now().strftime('%Y%m%d')}.csv",
        )
        df.to_csv(out_path, index=False)
        print(f"  Trades saved to: {out_path}")

    print()
    print("=" * 70)
    if results["expectancy"] > 1.0 and results["profit_factor"] > 1.3:
        print("  VERDICT: [YES] STRATEGY LOOKS PROMISING -- consider implementing")
    elif results["expectancy"] > 0:
        print("  VERDICT: [MARGINAL] EDGE EXISTS -- needs refinement before trading")
    else:
        print("  VERDICT: [NO EDGE] strategy loses money, do not trade")
    print("=" * 70)


if __name__ == "__main__":
    main()
