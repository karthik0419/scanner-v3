"""Run momentum backtest on full NSE EQ universe (~2000 stocks)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_momentum import backtest_stock, analyze_results
from data.nse_eq import fetch_nse_eq_universe
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import pandas as pd

stocks = fetch_nse_eq_universe()
print(f"Universe: {len(stocks)} stocks")
print("=" * 70)

all_trades = []
completed = 0
errors = 0

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(backtest_stock, s, "2y"): s for s in stocks}
    for future in as_completed(futures):
        symbol = futures[future]
        try:
            trades, sym = future.result()
            completed += 1
            if trades:
                all_trades.extend(trades)
                print(f"  [{completed}/{len(stocks)}] {sym}: {len(trades)} trades")
            if completed % 200 == 0:
                print(f"  ... {completed}/{len(stocks)} scanned, {len(all_trades)} trades so far")
        except Exception as e:
            errors += 1

print()
print(f"Scanned: {completed}, Errors: {errors}, Total trades: {len(all_trades)}")
print()

if not all_trades:
    print("No signals found.")
    sys.exit(0)

results = analyze_results(all_trades)

print("=" * 70)
print("  FULL NSE EQ MOMENTUM BACKTEST RESULTS")
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
print()

# Comparison
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

# Save
df = results["trades_df"]
out_path = os.path.join("results", f"momentum_full_nse_{datetime.now().strftime('%Y%m%d')}.csv")
df.to_csv(out_path, index=False)
print(f"  Trades saved to: {out_path}")
print()

# Verdict
print("=" * 70)
if results["expectancy"] > 1.0 and results["profit_factor"] > 1.3:
    print("  VERDICT: [YES] STRATEGY LOOKS PROMISING -- consider implementing")
elif results["expectancy"] > 0:
    print("  VERDICT: [MARGINAL] EDGE EXISTS -- needs refinement before trading")
else:
    print("  VERDICT: [NO EDGE] strategy loses money, do not trade")
print("=" * 70)
