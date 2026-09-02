"""
Sweep all entry filter variants across multiple thresholds.
Compare to baseline. Find the best variant + threshold combination.
Also run forward-test on paper tracker for each variant.
"""
import sys, os, time
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtester.engine import backtest_portfolio as baseline_bt
from backtester.engine_variants import backtest_portfolio as filter_bt
from entry_filter_variants import VARIANTS, score_entry
from data.loader import _fetch_nse


def load_stocks(filepath):
    with open(filepath) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def calc_stats(trades):
    if not trades:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "avg_win": 0,
                "avg_loss": 0, "expectancy": 0, "pf": 0, "max_dd": 0, "avg_days": 0}
    df = pd.DataFrame(trades)
    wins = df[df['pnl_pct'] > 0]
    losses = df[df['pnl_pct'] <= 0]
    avg_win = wins['pnl_pct'].mean() if len(wins) else 0
    avg_loss = losses['pnl_pct'].mean() if len(losses) else 0
    win_rate = len(wins) / len(df) * 100
    expectancy = df['pnl_pct'].mean()
    gross_profit = wins['pnl_pct'].sum() if len(wins) else 0
    gross_loss = abs(losses['pnl_pct'].sum()) if len(losses) else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    cum = df['pnl_pct'].cumsum()
    running_max = cum.expanding().max()
    dd = cum - running_max
    max_dd = dd.min()
    return {
        "trades": len(df), "wins": len(wins), "losses": len(losses),
        "win_rate": round(win_rate, 1), "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2), "expectancy": round(expectancy, 2),
        "pf": round(pf, 2), "max_dd": round(max_dd, 2),
        "avg_days": round(df['days_held'].mean(), 1),
    }


def forward_test_variant(variant, threshold):
    """Run forward test on paper tracker for a given variant."""
    tracker_path = os.path.join('..', 'results', 'paper_tracker.csv')
    if not os.path.exists(tracker_path):
        return None

    tracker = pd.read_csv(tracker_path)
    open_trades = tracker[tracker['current_status'] == 'OPEN'].copy()

    results = []
    for idx, row in open_trades.iterrows():
        sym = row['symbol']
        entry_price = float(row['entry_price'])
        current_price = float(row['current_price'])
        pnl = (current_price - entry_price) / entry_price * 100
        breakout = float(row.get('breakout_level', entry_price))

        try:
            df = _fetch_nse(sym.replace('.NS', ''), days=400)
            if df is None or len(df) < 60:
                continue
            df.index = pd.to_datetime(df.index)
            scan_date = pd.to_datetime(row.get('scan_date', ''), errors='coerce')
            if pd.isna(scan_date):
                mask = df.index <= df.index[-60]
            else:
                mask = df.index <= scan_date
            df_slice = df[mask].copy()
            if len(df_slice) < 60:
                continue

            score, _ = score_entry(df_slice, breakout, variant=variant)
            results.append({
                'symbol': sym, 'pnl': pnl, 'score': score,
                'passed': score >= threshold,
            })
        except:
            continue

    if not results:
        return None

    passed = [r for r in results if r['passed']]
    filtered = [r for r in results if not r['passed']]
    winners = [r for r in results if r['pnl'] > 0]
    losers = [r for r in results if r['pnl'] <= 0]

    tp = sum(1 for r in passed if r['pnl'] > 0)
    fp = sum(1 for r in passed if r['pnl'] <= 0)
    fn = sum(1 for r in filtered if r['pnl'] > 0)
    tn = sum(1 for r in filtered if r['pnl'] <= 0)

    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0

    avg_pnl_passed = np.mean([r['pnl'] for r in passed]) if passed else 0
    avg_pnl_filtered = np.mean([r['pnl'] for r in filtered]) if filtered else 0

    return {
        'total': len(results), 'passed': len(passed), 'filtered': len(filtered),
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'precision': round(precision, 1), 'recall': round(recall, 1),
        'avg_pnl_passed': round(avg_pnl_passed, 2),
        'avg_pnl_filtered': round(avg_pnl_filtered, 2),
        'winners_total': len(winners), 'losers_total': len(losers),
    }


def main():
    stocks_file = sys.argv[1] if len(sys.argv) > 1 else "nifty200.txt"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    symbols = load_stocks(stocks_file)
    print(f"\nStocks: {len(symbols)} | Years: {years}")
    print(f"Variants: {list(VARIANTS.keys())}")
    print()

    # Baseline (only once)
    print("=" * 90)
    print("  BASELINE (no filter)")
    print("=" * 90)
    t0 = time.time()
    baseline_trades = baseline_bt(symbols, years=years, min_score=50, scan_every=5, atr_stop=True)
    baseline_stats = calc_stats(baseline_trades)
    print(f"\n  {baseline_stats['trades']} trades in {time.time()-t0:.0f}s")

    # Test each variant at thresholds 40, 45, 50
    thresholds = [40, 45, 50]
    all_results = []

    for variant_name in VARIANTS:
        for thresh in thresholds:
            print()
            print("=" * 90)
            print(f"  VARIANT: {variant_name} | threshold={thresh}")
            print(f"  {VARIANTS[variant_name]['desc']}")
            print("=" * 90)
            t0 = time.time()
            trades = filter_bt(symbols, years=years, min_score=50, scan_every=5,
                               atr_stop=True, entry_filter_threshold=thresh,
                               filter_variant=variant_name)
            stats = calc_stats(trades)
            stats['variant'] = variant_name
            stats['threshold'] = thresh
            stats['time'] = round(time.time() - t0, 0)
            all_results.append(stats)
            print(f"\n  {stats['trades']} trades in {stats['time']}s")

    # --- BACKTEST SUMMARY TABLE ---
    print()
    print("=" * 120)
    print("  BACKTEST SUMMARY — ALL VARIANTS")
    print("=" * 120)
    print()
    print(f"  {'Variant':<20} {'Thresh':>6} {'Trades':>7} {'WinR%':>6} {'AvgWin':>7} {'AvgLoss':>8} {'Expect':>7} {'PF':>6} {'MaxDD':>8} {'Days':>5}")
    print("  " + "-" * 100)

    # Baseline row
    b = baseline_stats
    print(f"  {'BASELINE':<20} {'0':>6} {b['trades']:>7} {b['win_rate']:>6.1f} {b['avg_win']:>6.2f}% {b['avg_loss']:>7.2f}% {b['expectancy']:>6.2f}% {b['pf']:>5.2f} {b['max_dd']:>7.1f}% {b['avg_days']:>5.1f}")

    for s in all_results:
        print(f"  {s['variant']:<20} {s['threshold']:>6} {s['trades']:>7} {s['win_rate']:>6.1f} {s['avg_win']:>6.2f}% {s['avg_loss']:>7.2f}% {s['expectancy']:>6.2f}% {s['pf']:>5.2f} {s['max_dd']:>7.1f}% {s['avg_days']:>5.1f}")

    # --- FORWARD TEST ---
    print()
    print("=" * 120)
    print("  FORWARD TEST — Paper Tracker (21 open trades)")
    print("=" * 120)
    print()
    print(f"  {'Variant':<20} {'Thresh':>6} {'Passed':>7} {'Filter':>7} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'Prec%':>6} {'Rec%':>6} {'P&L_pass':>9} {'P&L_filt':>9}")
    print("  " + "-" * 110)

    forward_results = []
    for variant_name in VARIANTS:
        for thresh in thresholds:
            ft = forward_test_variant(variant_name, thresh)
            if ft:
                print(f"  {variant_name:<20} {thresh:>6} {ft['passed']:>7} {ft['filtered']:>7} {ft['tp']:>4} {ft['fp']:>4} {ft['fn']:>4} {ft['tn']:>4} {ft['precision']:>6.1f} {ft['recall']:>6.1f} {ft['avg_pnl_passed']:>+8.2f}% {ft['avg_pnl_filtered']:>+8.2f}%")
                forward_results.append({
                    'variant': variant_name, 'threshold': thresh, **ft
                })

    # --- BEST VARIANTS ---
    print()
    print("=" * 120)
    print("  BEST VARIANTS (by category)")
    print("=" * 120)

    # Best backtest expectancy (with >=200 trades)
    sig_bt = [s for s in all_results if s['trades'] >= 200]
    if sig_bt:
        best_bt = max(sig_bt, key=lambda x: x['expectancy'])
        print(f"\n  Best backtest expectancy (>=200 trades):")
        print(f"    {best_bt['variant']} @ {best_bt['threshold']} — exp={best_bt['expectancy']}%, WR={best_bt['win_rate']}%, PF={best_bt['pf']}, trades={best_bt['trades']}")

    # Best forward-test recall (kept most winners) with precision > 60%
    sig_ft = [f for f in forward_results if f['precision'] >= 60 and f['passed'] >= 5]
    if sig_ft:
        best_ft = max(sig_ft, key=lambda x: x['recall'])
        print(f"\n  Best forward-test recall (precision>=60%, passed>=5):")
        print(f"    {best_ft['variant']} @ {best_ft['threshold']} — recall={best_ft['recall']}%, precision={best_ft['precision']}%, passed={best_ft['passed']}/{best_ft['total']}")
    else:
        print(f"\n  No variant achieved precision>=60% with passed>=5. Filter too aggressive on live trades.")

    # Best balance: backtest expectancy + forward-test recall
    print(f"\n  Combined score (backtest expectancy * forward recall / 100):")
    combined = []
    for bt in all_results:
        for ft in forward_results:
            if bt['variant'] == ft['variant'] and bt['threshold'] == ft['threshold']:
                if ft['recall'] > 0 and bt['trades'] >= 200:
                    score = bt['expectancy'] * ft['recall'] / 100
                    combined.append((bt['variant'], bt['threshold'], score, bt, ft))
    combined.sort(key=lambda x: -x[2])
    for var, thresh, score, bt, ft in combined[:5]:
        print(f"    {var:<20} @ {thresh} — combined={score:.2f} (bt_exp={bt['expectancy']}%, ft_recall={ft['recall']}%, ft_prec={ft['precision']}%)")

    # Save
    pd.DataFrame(all_results).to_csv("variant_backtest_results.csv", index=False)
    pd.DataFrame(forward_results).to_csv("variant_forward_results.csv", index=False)
    print(f"\n  Saved variant_backtest_results.csv, variant_forward_results.csv")


if __name__ == "__main__":
    main()
