"""
Sweep multiple entry filter thresholds on nifty200, 2yr.
Find the sweet spot between trade count and expectancy improvement.
"""
import sys, os, time
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtester.engine import backtest_portfolio as baseline_bt
from backtester.engine_with_filter import backtest_portfolio as filter_bt
from run_comparison import calc_stats, load_stocks


def main():
    stocks_file = sys.argv[1] if len(sys.argv) > 1 else "nifty200.txt"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    symbols = load_stocks(stocks_file)
    print(f"\nSweeping entry filter thresholds on {len(symbols)} stocks, {years}yr\n")

    # Baseline first (only once)
    print("=" * 80)
    print("  BASELINE (no filter)")
    print("=" * 80)
    t0 = time.time()
    baseline_trades = baseline_bt(symbols, years=years, min_score=50, scan_every=5, atr_stop=True)
    print(f"\n  {len(baseline_trades)} trades in {time.time()-t0:.0f}s")
    baseline_stats = calc_stats(baseline_trades)

    # Sweep thresholds
    thresholds = [0, 30, 40, 45, 50, 55, 60, 65, 70]
    results = []

    for thresh in thresholds:
        print()
        print("=" * 80)
        print(f"  THRESHOLD = {thresh}")
        print("=" * 80)
        t0 = time.time()
        if thresh == 0:
            trades = baseline_trades  # reuse
        else:
            trades = filter_bt(symbols, years=years, min_score=50, scan_every=5,
                               atr_stop=True, entry_filter_threshold=thresh)
        stats = calc_stats(trades)
        stats['threshold'] = thresh
        stats['time'] = round(time.time() - t0, 0)
        results.append(stats)
        print(f"  {stats['trades']} trades in {stats['time']}s")

    # Summary table
    print()
    print("=" * 100)
    print("  THRESHOLD SWEEP SUMMARY")
    print("=" * 100)
    print()
    print(f"  {'Thresh':>6}  {'Trades':>7}  {'WinR%':>6}  {'AvgWin':>7}  {'AvgLoss':>8}  {'Expect':>7}  {'PF':>6}  {'MaxDD':>7}  {'Days':>5}")
    print("  " + "-" * 80)

    for s in results:
        print(f"  {s['threshold']:>6}  {s['trades']:>7}  {s['win_rate']:>6.1f}  {s['avg_win']:>6.2f}%  {s['avg_loss']:>7.2f}%  {s['expectancy']:>6.2f}%  {s['pf']:>5.2f}  {s['max_dd']:>6.1f}%  {s['avg_days']:>5.1f}")

    # Find best
    print()
    best_exp = max(results, key=lambda x: x['expectancy'])
    best_pf = max(results, key=lambda x: x['pf'])
    best_wr = max(results, key=lambda x: x['win_rate'])

    # Best with minimum 100 trades (statistical significance)
    sig_results = [r for r in results if r['trades'] >= 100]
    if sig_results:
        best_sig = max(sig_results, key=lambda x: x['expectancy'])
        print(f"  Best expectancy (all):     thresh={best_exp['threshold']}  exp={best_exp['expectancy']}%  trades={best_exp['trades']}")
        print(f"  Best PF (all):             thresh={best_pf['threshold']}  PF={best_pf['pf']}  trades={best_pf['trades']}")
        print(f"  Best win rate (all):       thresh={best_wr['threshold']}  WR={best_wr['win_rate']}%  trades={best_wr['trades']}")
        print(f"  Best expectancy (>=100 trades): thresh={best_sig['threshold']}  exp={best_sig['expectancy']}%  trades={best_sig['trades']}")
    else:
        print(f"  WARNING: No threshold produced >=100 trades. Filter may be too aggressive.")
        print(f"  Best expectancy: thresh={best_exp['threshold']}  exp={best_exp['expectancy']}%  trades={best_exp['trades']}")

    # Save sweep results
    sweep_df = pd.DataFrame(results)
    sweep_df.to_csv("sweep_results.csv", index=False)
    print(f"\n  Saved sweep_results.csv")


if __name__ == "__main__":
    main()
