"""Find trades where SL was hit but the stock later reached T1/T2.
This tells us if our stops are too tight — the trade would have been a winner
if we'd held on. We re-scan the price data after each SL exit."""
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data.loader import _fetch_nse

v3 = pd.read_csv("F:/projects/claude/scanner-v3/results/backtest_v3.csv")

# Only look at stop-loss exits
sl_trades = v3[v3["exit_reason"] == "Stop Loss"].copy()
print(f"=== ANALYSIS: SL exits that would have hit target ===")
print(f"Total SL exits: {len(sl_trades)}\n")

# For each SL exit, check if the stock reached T1 or T2 within MAX_HOLD days after SL hit
# We need to re-fetch price data for each symbol
whipsaw_results = []
checked = 0
skipped = 0

for idx, trade in sl_trades.iterrows():
    sym = trade["symbol"]
    exit_date_str = trade["exit_date"]
    t1 = trade["target_1"]
    t2 = trade["target_2"]
    sl_price = trade["stop_loss"]
    entry_price = trade["entry_price"]
    
    try:
        exit_date = pd.to_datetime(exit_date_str)
    except:
        skipped += 1
        continue
    
    checked += 1
    if checked % 200 == 0:
        print(f"  ...checked {checked}/{len(sl_trades)}")
    
    # Fetch 60 days of data after the SL exit
    try:
        df = _fetch_nse(sym.replace(".NS", ""), days=365*3)
        if df is None or df.empty:
            skipped += 1
            continue
        
        # Get data AFTER the SL exit date
        df_after = df[df.index > exit_date]
        if len(df_after) < 5:
            skipped += 1
            continue
        
        # Check next 30 bars (about 30 trading days)
        df_window = df_after.head(30)
        
        high_after = float(df_window["High"].max())
        low_after = float(df_window["Low"].min())
        close_after = float(df_window["Close"].iloc[-1])
        
        # Did it reach T1?
        hit_t1 = high_after >= t1
        # Did it reach T2?
        hit_t2 = high_after >= t2
        # Did it go even lower before recovering?
        went_lower = low_after < sl_price
        
        if hit_t1:
            # This was a whipsaw — SL hit but stock recovered to target
            days_to_t1 = (df_window.index[df_window["High"] >= t1][0] - exit_date).days if hit_t1 else 0
            pnl_if_held = (t1 - entry_price) / entry_price * 100
            whipsaw_results.append({
                "symbol": sym,
                "pattern": trade["pattern"],
                "entry": entry_price,
                "sl": sl_price,
                "t1": t1,
                "t2": t2,
                "sl_pnl": trade["pnl_pct"],
                "hit_t1": hit_t1,
                "hit_t2": hit_t2,
                "went_lower": went_lower,
                "low_after_sl": low_after,
                "days_to_t1": days_to_t1,
                "pnl_if_held_to_t1": round(pnl_if_held, 2),
                "close_30d_after": close_after,
            })
    except Exception as e:
        skipped += 1
        continue

print(f"\nChecked: {checked} | Skipped: {skipped}")
print(f"Whipsaws (SL hit but T1 reached later): {len(whipsaw_results)}")
print(f"Whipsaw rate: {len(whipsaw_results)/checked*100:.1f}% of SL exits\n")

if whipsaw_results:
    df_w = pd.DataFrame(whipsaw_results)
    
    # Summary stats
    print(f"--- WHIPSAW SUMMARY ---")
    print(f"  Total whipsaws:        {len(df_w)}")
    print(f"  Also hit T2:           {df_w['hit_t2'].sum()}")
    print(f"  Went lower before T1:  {df_w['went_lower'].sum()}")
    print(f"  Avg days to T1:        {df_w['days_to_t1'].mean():.1f}")
    print(f"  Avg SL loss:           {df_w['sl_pnl'].mean():.2f}%")
    print(f"  Avg P&L if held to T1: +{df_w['pnl_if_held_to_t1'].mean():.2f}%")
    print(f"  Avg further drop:      {((df_w['low_after_sl'] - df_w['sl']) / df_w['sl'] * 100).mean():.2f}% below SL")
    
    # By pattern
    print(f"\n--- WHIPSAWS BY PATTERN ---")
    pat_stats = df_w.groupby("pattern").agg(
        whipsaws=("symbol", "count"),
        avg_sl_loss=("sl_pnl", "mean"),
        avg_pnl_if_held=("pnl_if_held_to_t1", "mean"),
        avg_days_to_t1=("days_to_t1", "mean"),
        went_lower_pct=("went_lower", "mean"),
    )
    for pat, row in pat_stats.iterrows():
        print(f"  {pat:<25} {int(row['whipsaws']):>3} whipsaws | "
              f"SL: {row['avg_sl_loss']:.2f}% | if held: +{row['avg_pnl_if_held']:.2f}% | "
              f"days: {row['avg_days_to_t1']:.0f} | went lower: {row['went_lower_pct']*100:.0f}%")
    
    # Top 20 worst whipsaws (biggest difference between SL loss and T1 gain)
    print(f"\n--- TOP 20 WORST WHIPSAWS (biggest missed opportunity) ---")
    df_w["missed_pnl"] = df_w["pnl_if_held_to_t1"] - df_w["sl_pnl"]
    top20 = df_w.nlargest(20, "missed_pnl")
    print(f"  {'Symbol':<18} {'Pattern':<22} {'SL%':>7} {'If held%':>9} {'Missed%':>8} {'Days':>5} {'Lower?':>7}")
    for _, r in top20.iterrows():
        print(f"  {r['symbol']:<18} {r['pattern']:<22} {r['sl_pnl']:>+6.2f}% {r['pnl_if_held_to_t1']:>+8.2f}% {r['missed_pnl']:>+7.2f}% {r['days_to_t1']:>5.0f} {'Y' if r['went_lower'] else 'N':>7}")
    
    # How many went lower before recovering? (would need wider stop)
    went_lower = df_w[df_w["went_lower"]]
    print(f"\n--- WENT LOWER BEFORE RECOVERING ---")
    print(f"  {len(went_lower)}/{len(df_w)} whipsaws went below SL before recovering to T1")
    if len(went_lower) > 0:
        avg_extra_drop = ((went_lower["low_after_sl"] - went_lower["sl"]) / went_lower["sl"] * 100).mean()
        print(f"  Avg additional drop below SL: {avg_extra_drop:.2f}%")
        print(f"  This means a {1.5}x ATR stop would NOT have saved these — they needed to be wider")
    
    # Save full results
    df_w.to_csv("F:/projects/claude/scanner-v3/results/whipsaw_analysis.csv", index=False)
    print(f"\n  Full results saved: results/whipsaw_analysis.csv")
