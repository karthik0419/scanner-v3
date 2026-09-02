"""
Realistic Portfolio Simulation — Momentum Strategy
====================================================
Two modes:
  1. MULTI: Max 4 concurrent positions (Rs 12,500 each)
  2. ALL_IN: One stock at a time, all capital in, exit then next

Capital: Rs 50,000
Period: Last 6 months
Universe: Full NSE EQ (~2000 stocks)

REALISTIC ASSUMPTIONS:
- Entry at NEXT DAY OPEN (not same day close)
- Brokerage 0.03% each way + STT 0.025% on sell + slippage 0.1% each way
- Liquidity filter: avg volume >= 50k shares
- Integer shares only
"""

import os, sys, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# ============================================================
# CONFIG
# ============================================================
CAPITAL_START = 50000
MAX_POSITIONS = 4
MIN_POSITION_SIZE = 5000
BROKERAGE_PCT = 0.0003
STT_PCT = 0.00025
SLIPPAGE_PCT = 0.001
OTHER_FEES_PCT = 0.00005
PERIOD_MONTHS = 60  # 5 years (override with --months CLI arg)

UPTREND_LOOKBACK = 126
UPTREND_MIN = 0.30
HIGH_LOOKBACK = 50
PULLBACK_MIN = 0.05
PULLBACK_MAX = 0.10
VOLUME_LOOKBACK = 20
VOL_SURGE_MIN = 2.0
VOL_SURGE_MAX = 10.0
MIN_DAY_GAIN = 0.02
ATR_PERIOD = 14
ATR_MULT = 2.0
MAX_STOP_PCT = 0.08
TIME_EXIT_DAYS = 30
MIN_VOLUME = 50000


def calc_atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def fetch_data(symbol, period=None):
    """Fetch data. period is auto-calculated from PERIOD_MONTHS."""
    if period is None:
        # Need PERIOD_MONTHS of trading + ~8 months lookback buffer
        period = f"{max(PERIOD_MONTHS // 12 + 1, 1)}y"
    try:
        df = yf.Ticker(symbol).history(period=period)
        if df is None or len(df) < 150:
            return None
        df = df.dropna()
        cutoff = df.index[-1] - pd.Timedelta(days=PERIOD_MONTHS * 30 + 100)
        df = df[df.index >= cutoff]
        if len(df) < 150:
            return None
        return df
    except:
        return None


def detect_signals(df):
    close = df["Close"]; high = df["High"]; low = df["Low"]; volume = df["Volume"]
    open_ = df["Open"]
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
        signal_date = df.index[i]
        six_months_ago = df.index[-1] - pd.Timedelta(days=PERIOD_MONTHS * 30)
        if signal_date < six_months_ago:
            continue

        if pd.isna(ret_6mo.iloc[i]) or ret_6mo.iloc[i] < UPTREND_MIN: continue
        if pd.isna(pullback_pct.iloc[i]): continue
        pb = pullback_pct.iloc[i]
        if pb > -PULLBACK_MIN or pb < -PULLBACK_MAX: continue
        if pd.isna(vol_ratio.iloc[i]) or vol_ratio.iloc[i] < VOL_SURGE_MIN: continue
        if vol_ratio.iloc[i] > VOL_SURGE_MAX: continue
        if close.iloc[i] <= close.iloc[i - 1]: continue
        if daily_ret.iloc[i] < MIN_DAY_GAIN: continue

        avg_vol_shares = float(avg_vol.iloc[i])
        if avg_vol_shares < MIN_VOLUME: continue

        if i + 1 >= len(df): continue
        entry_price = float(open_.iloc[i + 1])
        if entry_price <= 0 or pd.isna(entry_price): continue

        entry_price_slipped = entry_price * (1 + SLIPPAGE_PCT)
        atr_val = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else entry_price * 0.04
        stop = entry_price_slipped - (ATR_MULT * atr_val)
        stop_pct = (entry_price_slipped - stop) / entry_price_slipped
        if stop_pct > MAX_STOP_PCT:
            stop = entry_price_slipped * (1 - MAX_STOP_PCT)
            stop_pct = MAX_STOP_PCT

        target = float(rolling_high.iloc[i])
        if target <= entry_price_slipped: continue

        signals.append({
            "signal_date": df.index[i],
            "entry_date": df.index[i + 1],
            "entry_idx": i + 1,
            "entry_price": round(entry_price_slipped, 2),
            "raw_entry": round(entry_price, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "stop_pct": round(stop_pct * 100, 2),
            "pullback_pct": round(pb * 100, 2),
            "vol_ratio": round(float(vol_ratio.iloc[i]), 2),
            "daily_gain": round(float(daily_ret.iloc[i]) * 100, 2),
            "ret_6mo": round(float(ret_6mo.iloc[i]) * 100, 2),
            "avg_vol": int(avg_vol_shares),
        })
    return signals


def simulate_trade(df, signal):
    entry = signal["entry_price"]; stop = signal["stop"]; target = signal["target"]
    start = signal["entry_idx"]
    end = min(start + TIME_EXIT_DAYS, len(df))

    for j in range(start, end):
        day_low = float(df["Low"].iloc[j]); day_high = float(df["High"].iloc[j])
        days_held = j - start + 1

        if day_low <= stop:
            exit_price = stop * (1 - SLIPPAGE_PCT)
            return {"exit_date": df.index[j], "exit_price": round(exit_price, 2),
                    "days_held": days_held, "status": "LOSS",
                    "pnl_pct_raw": round((exit_price - entry) / entry * 100, 2)}

        if day_high >= target:
            exit_price = target * (1 - SLIPPAGE_PCT)
            return {"exit_date": df.index[j], "exit_price": round(exit_price, 2),
                    "days_held": days_held, "status": "WIN",
                    "pnl_pct_raw": round((exit_price - entry) / entry * 100, 2)}

    final_close = float(df["Close"].iloc[end - 1])
    exit_price = final_close * (1 - SLIPPAGE_PCT)
    return {"exit_date": df.index[end - 1], "exit_price": round(exit_price, 2),
            "days_held": end - start, "status": "TIME_EXIT",
            "pnl_pct_raw": round((exit_price - entry) / entry * 100, 2)}


def calc_fees(cost, exit_value):
    entry_fee = cost * BROKERAGE_PCT + cost * OTHER_FEES_PCT
    exit_fee = exit_value * BROKERAGE_PCT + exit_value * STT_PCT + exit_value * OTHER_FEES_PCT
    return entry_fee + exit_fee


def run_simulation(all_signals, mode="multi"):
    """Run portfolio simulation. mode='multi' (4 positions) or 'all_in' (1 at a time)."""
    all_signals = sorted(all_signals, key=lambda s: s["entry_date"])

    capital = CAPITAL_START
    closed_trades = []
    max_capital = capital
    max_drawdown = 0

    # Track active position(s) and their exit dates
    active = []  # list of {"exit_date": pd.Timestamp, "cost": float}

    for sig in all_signals:
        entry_date = sig["entry_date"]

        # Remove exited positions
        active = [p for p in active if p["exit_date"] >= entry_date]

        if mode == "multi":
            if len(active) >= MAX_POSITIONS:
                continue
            free_capital = capital - sum(p["cost"] for p in active)
            position_size = min(free_capital, capital / MAX_POSITIONS)
        else:  # all_in
            if len(active) > 0:
                continue  # wait until current position exits
            position_size = capital  # all in

        if position_size < MIN_POSITION_SIZE:
            continue

        result = simulate_trade(sig["df"], sig)
        if result is None:
            continue

        entry = sig["entry_price"]
        shares = int(position_size / entry)
        if shares < 1:
            continue

        cost = shares * entry
        exit_value = shares * result["exit_price"]
        gross_pnl = exit_value - cost
        fees = calc_fees(cost, exit_value)
        net_pnl = gross_pnl - fees
        net_pnl_pct = (net_pnl / cost) * 100

        capital += net_pnl

        if capital > max_capital:
            max_capital = capital
        dd = (capital - max_capital) / max_capital * 100
        if dd < max_drawdown:
            max_drawdown = dd

        trade = {
            "symbol": sig["symbol"],
            "signal_date": sig["signal_date"].strftime("%Y-%m-%d"),
            "entry_date": sig["entry_date"].strftime("%Y-%m-%d"),
            "exit_date": result["exit_date"].strftime("%Y-%m-%d"),
            "entry_price": entry,
            "exit_price": result["exit_price"],
            "shares": shares,
            "cost": round(cost, 2),
            "gross_pnl": round(gross_pnl, 2),
            "fees": round(fees, 2),
            "net_pnl": round(net_pnl, 2),
            "net_pnl_pct": round(net_pnl_pct, 2),
            "days_held": result["days_held"],
            "status": result["status"],
            "pullback_pct": sig["pullback_pct"],
            "vol_ratio": sig["vol_ratio"],
            "ret_6mo": sig["ret_6mo"],
            "capital_after": round(capital, 2),
        }
        closed_trades.append(trade)
        active.append({"exit_date": result["exit_date"], "cost": cost})

    return closed_trades, capital, max_drawdown


def format_results(closed_trades, capital, max_drawdown, mode_label):
    df = pd.DataFrame(closed_trades)
    total_return = ((capital / CAPITAL_START) - 1) * 100
    net_profit = capital - CAPITAL_START

    lines = []
    lines.append(f"  MODE: {mode_label}")
    lines.append(f"  Starting capital:  Rs {CAPITAL_START:,}")
    lines.append(f"  Final capital:     Rs {capital:,.2f}")
    lines.append(f"  Total return:      {total_return:+.2f}%")
    lines.append(f"  Net P&L:           Rs {net_profit:,.2f}")
    lines.append(f"  Total trades:      {len(closed_trades)}")
    lines.append(f"  Max drawdown:      {max_drawdown:.2f}%")

    if len(closed_trades) > 0:
        wins = df[df["net_pnl"] > 0]
        losses = df[df["net_pnl"] <= 0]
        lines.append(f"  Wins: {len(wins)}  Losses: {len(losses)}")
        if len(closed_trades) > 0:
            lines.append(f"  Win rate: {len(wins)/len(closed_trades)*100:.1f}%")
        if len(wins) > 0:
            lines.append(f"  Avg win:  Rs {wins['net_pnl'].mean():,.2f} ({wins['net_pnl_pct'].mean():+.2f}%)")
        if len(losses) > 0:
            lines.append(f"  Avg loss: Rs {losses['net_pnl'].mean():,.2f} ({losses['net_pnl_pct'].mean():+.2f}%)")
        lines.append(f"  Total fees: Rs {df['fees'].sum():,.2f}")
        lines.append(f"  Avg days held: {df['days_held'].mean():.1f}")
        lines.append("")

        # Status breakdown
        lines.append("  Status breakdown:")
        for status, count in df["status"].value_counts().items():
            subset = df[df["status"] == status]
            lines.append(f"    {status:12s}: {count:3d} trades  avg Rs {subset['net_pnl'].mean():>+8.2f} ({subset['net_pnl_pct'].mean():>+6.2f}%)")
        lines.append("")

        # Monthly or yearly depending on period length
        if PERIOD_MONTHS <= 12:
            df["period"] = pd.to_datetime(df["entry_date"]).dt.to_period("M")
            lines.append("  Monthly:")
        else:
            df["period"] = pd.to_datetime(df["entry_date"]).dt.to_period("Q")
            lines.append("  Quarterly:")

        period_grp = df.groupby("period").agg(
            trades=("net_pnl", "count"),
            wins=("net_pnl", lambda x: (x > 0).sum()),
            net_pnl=("net_pnl", "sum"),
            end_capital=("capital_after", "last"),
        ).reset_index()
        for _, r in period_grp.iterrows():
            lines.append(f"    {str(r['period']):>10s}  {r['trades']:>3d} trades  {r['wins']:>2d}W  Rs {r['net_pnl']:>+9.2f}  Cap: Rs {r['end_capital']:>9.2f}")
        lines.append("")

        # All trades (limit to last 30 for long periods to keep output manageable)
        if PERIOD_MONTHS > 12:
            lines.append(f"  LAST 30 TRADES (of {len(closed_trades)} total):")
            show_trades = closed_trades[-30:]
            start_num = len(closed_trades) - 29
        else:
            lines.append("  ALL TRADES:")
            show_trades = closed_trades
            start_num = 1
        for i, t in enumerate(show_trades):
            lines.append(f"    {start_num+i:>3d}. {t['symbol']:>16s}  {t['entry_date']} -> {t['exit_date']}  {t['days_held']:>2d}d  {t['status']:>9s}  Rs {t['cost']:>8.2f} -> Rs {t['net_pnl']:>+8.2f} ({t['net_pnl_pct']:>+6.2f}%)  Cap: Rs {t['capital_after']:>9.2f}")

    return "\n".join(lines), df


def main():
    import argparse
    global PERIOD_MONTHS
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=PERIOD_MONTHS, help="Number of months to simulate")
    parser.add_argument("--workers", type=int, default=10, help="Parallel workers")
    args = parser.parse_args()

    PERIOD_MONTHS = args.months

    from data.nse_eq import fetch_nse_eq_universe
    stocks = fetch_nse_eq_universe()
    print(f"Universe: {len(stocks)} stocks")
    print(f"Capital: Rs {CAPITAL_START:,}")
    print(f"Period: Last {PERIOD_MONTHS} months ({PERIOD_MONTHS/12:.1f} years)")
    print(f"Strategy: Golden config (pullback 5-10%, vol 2-10x, no re-entry)")
    print(f"Fees: {BROKERAGE_PCT*100}% brokerage + {STT_PCT*100}% STT + {SLIPPAGE_PCT*100}% slippage each way")
    print("=" * 70)

    # Phase 1: Fetch data and detect signals
    all_signals = []
    completed = 0
    stock_data = {}  # symbol -> df

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(fetch_data, s): s for s in stocks}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                df = future.result()
                completed += 1
                if df is not None:
                    stock_data[symbol] = df
                    sigs = detect_signals(df)
                    for sig in sigs:
                        sig["symbol"] = symbol
                        sig["df"] = df
                        all_signals.append(sig)
                if completed % 200 == 0:
                    print(f"  ... {completed}/{len(stocks)} scanned, {len(all_signals)} signals")
            except:
                pass

    print(f"\nTotal signals: {len(all_signals)}")

    if not all_signals:
        print(f"No signals in last {PERIOD_MONTHS} months.")
        return

    # Phase 2: Run both modes
    print("\n" + "=" * 70)
    print("  MODE 1: MULTI (max 4 concurrent positions)")
    print("=" * 70)
    trades_multi, cap_multi, dd_multi = run_simulation(all_signals, mode="multi")
    report_multi, df_multi = format_results(trades_multi, cap_multi, dd_multi, "MULTI (4 positions)")
    print(report_multi)

    print("\n" + "=" * 70)
    print("  MODE 2: ALL-IN (one stock at a time, full capital)")
    print("=" * 70)
    trades_allin, cap_allin, dd_allin = run_simulation(all_signals, mode="all_in")
    report_allin, df_allin = format_results(trades_allin, cap_allin, dd_allin, "ALL-IN (1 stock)")
    print(report_allin)

    # Comparison
    print("\n" + "=" * 70)
    print("  COMPARISON")
    print("=" * 70)
    fd_return = CAPITAL_START * 0.07 * (PERIOD_MONTHS / 12)
    print(f"  Bank FD (7% annual, 6mo):       Rs {CAPITAL_START + fd_return:,.2f}  (+{fd_return/CAPITAL_START*100:.1f}%)")
    print(f"  MULTI (4 positions):            Rs {cap_multi:,.2f}  ({((cap_multi/CAPITAL_START)-1)*100:+.1f}%)  DD: {dd_multi:.1f}%  Trades: {len(trades_multi)}")
    print(f"  ALL-IN (1 stock at a time):     Rs {cap_allin:,.2f}  ({((cap_allin/CAPITAL_START)-1)*100:+.1f}%)  DD: {dd_allin:.1f}%  Trades: {len(trades_allin)}")

    # Save
    if df_multi is not None:
        out1 = os.path.join("results", f"portfolio_multi_{datetime.now().strftime('%Y%m%d')}.csv")
        df_multi.to_csv(out1, index=False)
        print(f"\n  Saved: {out1}")
    if df_allin is not None:
        out2 = os.path.join("results", f"portfolio_allin_{datetime.now().strftime('%Y%m%d')}.csv")
        df_allin.to_csv(out2, index=False)
        print(f"  Saved: {out2}")

    # Send to Telegram
    send_telegram_report(report_multi, report_allin, cap_multi, cap_allin, dd_multi, dd_allin,
                         len(trades_multi), len(trades_allin), df_multi, df_allin)


def send_telegram_report(report_multi, report_allin, cap_multi, cap_allin, dd_multi, dd_allin,
                         n_multi, n_allin, df_multi=None, df_allin=None):
    from telegram_notify import send_telegram, _get_credentials
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        print("  [Telegram] Missing credentials — skipping.")
        return

    years = PERIOD_MONTHS / 12
    fd_return = CAPITAL_START * 0.07 * years
    ret_multi = ((cap_multi / CAPITAL_START) - 1) * 100
    ret_allin = ((cap_allin / CAPITAL_START) - 1) * 100
    cagr_multi = (((cap_multi / CAPITAL_START) ** (1 / years)) - 1) * 100 if years > 0 else 0
    cagr_allin = (((cap_allin / CAPITAL_START) ** (1 / years)) - 1) * 100 if years > 0 else 0

    # Yearly breakdown
    yearly_lines = ""
    if df_multi is not None and len(df_multi) > 0:
        df_multi_copy = df_multi.copy()
        df_multi_copy["year"] = pd.to_datetime(df_multi_copy["entry_date"]).dt.year
        yearly = df_multi_copy.groupby("year").agg(
            trades=("net_pnl", "count"),
            wins=("net_pnl", lambda x: (x > 0).sum()),
            pnl=("net_pnl", "sum"),
        ).reset_index()
        yearly_lines += "\n<b>YEARLY BREAKDOWN (MULTI mode):</b>\n"
        for _, r in yearly.iterrows():
            yearly_lines += f"  {r['year']}: {r['trades']} trades, {r['wins']}W, P&L Rs {r['pnl']:>+,.0f}\n"

    if df_allin is not None and len(df_allin) > 0:
        df_allin_copy = df_allin.copy()
        df_allin_copy["year"] = pd.to_datetime(df_allin_copy["entry_date"]).dt.year
        yearly_a = df_allin_copy.groupby("year").agg(
            trades=("net_pnl", "count"),
            wins=("net_pnl", lambda x: (x > 0).sum()),
            pnl=("net_pnl", "sum"),
        ).reset_index()
        yearly_lines += "\n<b>YEARLY BREAKDOWN (ALL-IN mode):</b>\n"
        for _, r in yearly_a.iterrows():
            yearly_lines += f"  {r['year']}: {r['trades']} trades, {r['wins']}W, P&L Rs {r['pnl']:>+,.0f}\n"

    msg = f"""<b>Momentum Strategy — Portfolio Simulation Results</b>
<b>Capital: Rs 50,000 | Period: Last {PERIOD_MONTHS} months ({years:.0f} years) | NSE EQ (~2000 stocks)</b>

<b>STRATEGY: Momentum Continuation (Golden config)</b>
- Uptrend 30%+ in 6mo, Pullback 5-10% from 50-day high
- Volume surge 2-10x, Daily gain 2%+
- Entry: next day open | SL: 2x ATR (8% cap) | Target: 50-day high
- Fees: 0.03% brokerage + 0.025% STT + 0.1% slippage each way

━━━━━━━━━━━━━━━━━━━
<b>MODE 1: MULTI (4 concurrent positions)</b>
━━━━━━━━━━━━━━━━━━━
Starting: Rs 50,000
Final:    Rs {cap_multi:,.2f}
Return:   {ret_multi:+.2f}% (CAGR: {cagr_multi:+.1f}%/yr)
P&L:      Rs {cap_multi - CAPITAL_START:,.2f}
Trades:   {n_multi}
Max DD:   {dd_multi:.2f}%

━━━━━━━━━━━━━━━━━━━
<b>MODE 2: ALL-IN (1 stock at a time)</b>
━━━━━━━━━━━━━━━━━━━
Starting: Rs 50,000
Final:    Rs {cap_allin:,.2f}
Return:   {ret_allin:+.2f}% (CAGR: {cagr_allin:+.1f}%/yr)
P&L:      Rs {cap_allin - CAPITAL_START:,.2f}
Trades:   {n_allin}
Max DD:   {dd_allin:.2f}%

━━━━━━━━━━━━━━━━━━━
<b>COMPARISON ({years:.0f} years)</b>
━━━━━━━━━━━━━━━━━━━
Bank FD (7%):     Rs {CAPITAL_START + fd_return:,.2f} (+{fd_return/CAPITAL_START*100:.1f}%)
MULTI (4 pos):    Rs {cap_multi:,.2f} ({ret_multi:+.1f}%, CAGR {cagr_multi:+.1f}%/yr)
ALL-IN (1 stock): Rs {cap_allin:,.2f} ({ret_allin:+.1f}%, CAGR {cagr_allin:+.1f}%/yr)

{yearly_lines}
━━━━━━━━━━━━━━━━━━━
Realistic: next-day entry, slippage, brokerage, STT, liquidity filter.
Survivorship bias: current NSE list only.
Not financial advice. For research only."""

    ok = send_telegram(token, chat_id, msg)
    print(f"\n  [Telegram] {'Sent successfully' if ok else 'Failed to send'}")


if __name__ == "__main__":
    main()
