"""Sweep ATR multipliers to find the optimal stop loss distance.
Tests 1.0x, 1.5x, 2.0x, 2.5x, 3.0x on backbone50 (2 years)."""
import sys, os, argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtester.engine import backtest_portfolio, _calc_atr, _apply_atr_stop, _detect_signal, _add_targets, _score, _close_trade, _data_is_sane, MAX_HOLD_DAYS
from data.loader import _fetch_nse, _resample_weekly

def backtest_with_multiplier(symbols, years=2, min_score=40, scan_every=5, atr_mult=1.5, max_risk=0.08):
    """Backtest with a specific ATR multiplier and max risk cap."""
    all_trades = []
    for sym in symbols:
        df = _fetch_nse(sym.replace(".NS", ""), days=years * 365)
        if df is None or len(df) < 150:
            continue
        if not _data_is_sane(df, sym):
            continue
        
        trades = []
        open_trade = None
        last_scan_idx = 0
        t1_hit = False
        trailing_stop = None
        
        for i in range(140, len(df)):
            current_date = df.index[i]
            row = df.iloc[i]
            low = float(row["Low"])
            high = float(row["High"])
            close = float(row["Close"])
            
            if open_trade is not None:
                entry_price = open_trade["entry_price"]
                days_held = (current_date - open_trade["entry_date"]).days
                effective_stop = trailing_stop if t1_hit else open_trade["stop_loss"]
                if low <= effective_stop:
                    trades.append(_close_trade(open_trade, effective_stop, current_date,
                                               "Trailing Stop" if t1_hit else "Stop Loss"))
                    open_trade = None; t1_hit = False; trailing_stop = None; continue
                if high >= open_trade["target_2"]:
                    trades.append(_close_trade(open_trade, open_trade["target_2"], current_date, "Target 2"))
                    open_trade = None; t1_hit = False; trailing_stop = None; continue
                if not t1_hit and high >= open_trade["target_1"]:
                    t1_trade = dict(open_trade)
                    t1_trade["quantity_pct"] = 50
                    trades.append(_close_trade(t1_trade, open_trade["target_1"], current_date, "Target 1"))
                    t1_hit = True; trailing_stop = entry_price; continue
                if days_held >= MAX_HOLD_DAYS:
                    trades.append(_close_trade(open_trade, close, current_date, "Time Exit"))
                    open_trade = None; t1_hit = False; trailing_stop = None; continue
            
            if open_trade is None and (i - last_scan_idx) >= scan_every:
                last_scan_idx = i
                df_slice = df.iloc[: i + 1].copy()
                df_weekly_slice = _resample_weekly(df_slice)
                result = _detect_signal(df_slice, df_weekly_slice)
                if result:
                    result = _add_targets(result)
                    
                    # Custom ATR stop with specific multiplier
                    cmp = result.get("cmp", 0)
                    current_stop = result.get("stop_loss", 0)
                    current_risk = (cmp - current_stop) / cmp if cmp else 0
                    
                    if current_risk > max_risk:
                        atr = _calc_atr(df_slice, period=14)
                        breakout = result.get("breakout", 0)
                        if atr > 0:
                            new_stop = round(breakout - (atr_mult * atr), 2)
                            if new_stop > 0 and new_stop < cmp:
                                max_stop = cmp * (1 - max_risk)
                                new_stop = max(new_stop, max_stop)
                                if (cmp - new_stop) / cmp <= max_risk:
                                    result["stop_loss"] = new_stop
                                else:
                                    result["stop_loss"] = round(max_stop, 2)
                            else:
                                result["stop_loss"] = round(cmp * (1 - max_risk), 2)
                        else:
                            result["stop_loss"] = round(cmp * (1 - max_risk), 2)
                    
                    score, rr = _score(result)
                    result["score"] = score
                    result["rr"] = rr
                    
                    cmp_val = result.get("cmp", 0)
                    stop_val = result.get("stop_loss", 0)
                    bo_val = result.get("breakout", 0)
                    risk_pct = (cmp_val - stop_val) / cmp_val * 100 if cmp_val else 0
                    if risk_pct > 10:
                        continue
                    dist_pct = abs(bo_val - cmp_val) / cmp_val * 100 if bo_val and cmp_val else 0
                    if bo_val > 0 and dist_pct > 8 and result.get("status") != "BREAKOUT":
                        continue
                    
                    if score >= min_score and rr > 0:
                        if i + 1 >= len(df):
                            continue
                        entry_price = float(df.iloc[i + 1]["Open"])
                        stop_loss = result["stop_loss"]
                        if stop_loss >= entry_price:
                            continue
                        open_trade = {
                            "symbol": sym, "pattern": result["pattern"],
                            "signal_date": current_date, "entry_date": df.index[i + 1],
                            "entry_price": entry_price, "stop_loss": stop_loss,
                            "target_1": result["target_1"], "target_2": result["target_2"],
                            "score": score, "rr": rr, "status": result.get("status", ""),
                            "atr": result.get("atr", 0), "exit_price": None, "exit_date": None,
                            "exit_reason": None, "pnl_pct": None, "result": None,
                            "days_held": None, "quantity_pct": 100,
                        }
        
        if open_trade is not None:
            trades.append(_close_trade(open_trade, float(df.iloc[-1]["Close"]), df.index[-1], "End of Data"))
        all_trades.extend(trades)
    return all_trades

def summarize(trades, label):
    if not trades:
        return {"label": label, "trades": 0}
    df = pd.DataFrame(trades)
    total = len(df)
    wins = (df["result"] == "WIN").sum()
    losses = (df["result"] == "LOSS").sum()
    avg_win = df.loc[df["result"] == "WIN", "pnl_pct"].mean() if wins else 0
    avg_loss = df.loc[df["result"] == "LOSS", "pnl_pct"].mean() if losses else 0
    win_rate = wins / total * 100 if total else 0
    expectancy = (wins/total * avg_win) + (losses/total * avg_loss) if total else 0
    gp = df.loc[df["pnl_pct"] > 0, "pnl_pct"].sum()
    gl = abs(df.loc[df["pnl_pct"] < 0, "pnl_pct"].sum())
    pf = gp / gl if gl > 0 else 0
    equity = (1 + df["pnl_pct"] / 100).cumprod()
    dd = ((equity - equity.cummax()) / equity.cummax() * 100).min()
    sl_count = (df["exit_reason"] == "Stop Loss").sum()
    t1_count = (df["exit_reason"] == "Target 1").sum()
    t2_count = (df["exit_reason"] == "Target 2").sum()
    avg_risk = ((df["entry_price"] - df["stop_loss"]) / df["entry_price"] * 100).mean()
    return {
        "label": label, "trades": total, "wins": wins, "losses": losses,
        "win_rate": round(win_rate, 1), "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2), "expectancy": round(expectancy, 2),
        "profit_factor": round(pf, 2), "max_drawdown": round(dd, 1),
        "sl_exits": sl_count, "t1_hits": t1_count, "t2_hits": t2_count,
        "avg_risk": round(avg_risk, 2),
    }

def load_stocks(filepath):
    with open(filepath) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]

def main():
    stocks = load_stocks("backbone50.txt")
    print(f"\n{'='*80}")
    print(f"  ATR MULTIPLIER SWEEP — backbone50 ({len(stocks)} stocks, 2 years)")
    print(f"{'='*80}")
    
    multipliers = [1.0, 1.5, 2.0, 2.5, 3.0]
    results = []
    
    for mult in multipliers:
        print(f"\n  Testing ATR multiplier = {mult}x...")
        trades = backtest_with_multiplier(stocks, years=2, min_score=40, scan_every=5, atr_mult=mult)
        s = summarize(trades, f"ATR {mult}x")
        results.append(s)
        print(f"    Trades: {s['trades']} | WR: {s['win_rate']}% | Exp: {s['expectancy']}% | "
              f"Avg loss: {s['avg_loss']}% | PF: {s['profit_factor']} | DD: {s['max_drawdown']}%")
    
    # Also test with no cap (pure structural stops)
    print(f"\n  Testing NO ATR (pure structural stops, no cap)...")
    trades = backtest_with_multiplier(stocks, years=2, min_score=40, scan_every=5, atr_mult=1.5, max_risk=1.0)
    s = summarize(trades, "No cap")
    results.append(s)
    print(f"    Trades: {s['trades']} | WR: {s['win_rate']}% | Exp: {s['expectancy']}% | "
          f"Avg loss: {s['avg_loss']}% | PF: {s['profit_factor']} | DD: {s['max_drawdown']}%")
    
    # Results table
    print(f"\n{'='*80}")
    print(f"  RESULTS TABLE")
    print(f"{'='*80}")
    print(f"  {'Mode':<12} {'Trades':>7} {'WR':>6} {'AvgWin':>8} {'AvgLoss':>8} {'Exp':>7} {'PF':>6} {'DD':>8} {'AvgRisk':>8} {'SL':>5} {'T1':>5} {'T2':>5}")
    print(f"  {'-'*95}")
    for r in results:
        print(f"  {r['label']:<12} {r['trades']:>7} {r['win_rate']:>5.1f}% {r['avg_win']:>+7.2f}% {r['avg_loss']:>+7.2f}% {r['expectancy']:>+6.2f}% {r['profit_factor']:>5.2f} {r['max_drawdown']:>+7.1f}% {r['avg_risk']:>7.2f}% {r['sl_exits']:>5} {r['t1_hits']:>5} {r['t2_hits']:>5}")
    
    # Find best
    best = max(results, key=lambda x: x.get("expectancy", 0))
    print(f"\n  BEST EXPECTANCY: {best['label']} (+{best['expectancy']}%/trade)")
    best_pf = max(results, key=lambda x: x.get("profit_factor", 0))
    print(f"  BEST PROFIT FACTOR: {best_pf['label']} ({best_pf['profit_factor']})")
    best_dd = max(results, key=lambda x: x.get("max_drawdown", -100))
    print(f"  BEST DRAWDOWN: {best_dd['label']} ({best_dd['max_drawdown']}%)")

if __name__ == "__main__":
    main()
