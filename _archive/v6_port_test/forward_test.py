"""
Forward-test simulation: apply entry filter to current paper tracker picks.

For each open trade, fetches daily data up to the entry date, calculates
the entry confirmation score, and checks whether the filter would have
allowed or rejected the trade. Then compares to actual P&L.
"""
import sys, os
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.loader import _fetch_nse
from entry_filter import score_entry

THRESHOLD = 50.0

def main():
    tracker_path = os.path.join('..', 'results', 'paper_tracker.csv')
    if not os.path.exists(tracker_path):
        print(f"Tracker not found at {tracker_path}")
        return

    tracker = pd.read_csv(tracker_path)
    # Only OPEN trades (already entered)
    open_trades = tracker[tracker['current_status'] == 'OPEN'].copy()
    # Also check WAITING_BREAKOUT — they haven't entered yet
    waiting = tracker[tracker['current_status'] == 'WAITING_BREAKOUT'].copy()

    print()
    print("=" * 110)
    print(f"  FORWARD-TEST: Entry Filter (threshold={THRESHOLD}) on Paper Tracker")
    print("=" * 110)
    print()
    print(f"  Open trades: {len(open_trades)}  |  Waiting breakout: {len(waiting)}")
    print()

    # --- Score each open trade at its entry date ---
    results = []
    for idx, row in open_trades.iterrows():
        sym = row['symbol']
        # Tracker has no entry_date column — derive from scan_date + days_held
        scan_date_str = str(row.get('scan_date', ''))
        days_held = int(row.get('days_held', 0))
        entry_date_str = scan_date_str  # scan_date is closest proxy to entry
        entry_price = float(row['entry_price'])
        stop = float(row['stop_loss'])
        t1 = float(row['target_1'])
        current_price = float(row['current_price'])
        pnl = (current_price - entry_price) / entry_price * 100
        pattern = row.get('pattern', '')

        # Fetch ~1 year of data ending around entry date
        try:
            df = _fetch_nse(sym.replace('.NS', ''), days=400)
            if df is None or len(df) < 60:
                results.append({
                    'symbol': sym, 'pattern': pattern, 'entry_date': entry_date_str,
                    'entry_price': entry_price, 'current_price': current_price,
                    'pnl_pct': round(pnl, 2), 'filter_score': -1,
                    'would_enter': 'NO DATA', 'breakout': 0,
                })
                continue

            # Find the entry date in the data
            entry_date = pd.to_datetime(entry_date_str, errors='coerce')
            if pd.isna(entry_date):
                # Try parsing with dayfirst
                for fmt in ['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y']:
                    try:
                        entry_date = pd.to_datetime(entry_date_str, format=fmt)
                        break
                    except:
                        continue

            if pd.isna(entry_date):
                results.append({
                    'symbol': sym, 'pattern': pattern, 'entry_date': entry_date_str,
                    'entry_price': entry_price, 'current_price': current_price,
                    'pnl_pct': round(pnl, 2), 'filter_score': -1,
                    'would_enter': 'BAD DATE', 'breakout': 0,
                })
                continue

            # Get data up to entry date (the signal would be generated ON or BEFORE entry)
            # Entry is at next day's open after signal, so signal is on entry_date - 1
            df.index = pd.to_datetime(df.index)
            mask = df.index <= entry_date
            df_slice = df[mask].copy()

            if len(df_slice) < 60:
                results.append({
                    'symbol': sym, 'pattern': pattern, 'entry_date': entry_date_str,
                    'entry_price': entry_price, 'current_price': current_price,
                    'pnl_pct': round(pnl, 2), 'filter_score': -1,
                    'would_enter': 'INSUFFICIENT', 'breakout': 0,
                })
                continue

            # Estimate breakout level from the tracker (use entry_price as proxy if not available)
            breakout = entry_price  # conservative — actual breakout may differ

            score, details = score_entry(df_slice, breakout)

            would_enter = 'YES' if score >= THRESHOLD else 'FILTERED OUT'

            results.append({
                'symbol': sym, 'pattern': pattern, 'entry_date': entry_date_str,
                'entry_price': entry_price, 'current_price': current_price,
                'pnl_pct': round(pnl, 2), 'filter_score': score,
                'would_enter': would_enter, 'breakout': breakout,
                'rsi': details.get('rsi', 0),
                'macd': details.get('macd', 0),
                'vol_spike': details.get('vol_spike', 0),
                'ma_align': details.get('ma_align', 0),
                'momentum': details.get('momentum', 0),
            })
        except Exception as e:
            results.append({
                'symbol': sym, 'pattern': pattern, 'entry_date': entry_date_str,
                'entry_price': entry_price, 'current_price': current_price,
                'pnl_pct': round(pnl, 2), 'filter_score': -1,
                'would_enter': f'ERROR: {str(e)[:30]}', 'breakout': 0,
            })

    # --- Print results ---
    print("  OPEN TRADES — Entry Filter Score at Entry Date")
    print("  " + "-" * 120)
    print(f"  {'Symbol':<16} {'Pattern':<22} {'Entry':>10} {'Now':>10} {'P&L%':>7} {'Score':>6} {'Verdict':<14} {'RSI':>5} {'MACD':>5} {'Vol':>5} {'MA':>5} {'Mom':>5}")
    print("  " + "-" * 120)

    # Sort by P&L descending
    results.sort(key=lambda x: -x['pnl_pct'])

    for r in results:
        if r['filter_score'] < 0:
            print(f"  {r['symbol']:<16} {r['pattern']:<22} {r['entry_price']:>10.2f} {r['current_price']:>10.2f} {r['pnl_pct']:>+6.1f}% {'N/A':>6} {r['would_enter']:<14}")
        else:
            print(f"  {r['symbol']:<16} {r['pattern']:<22} {r['entry_price']:>10.2f} {r['current_price']:>10.2f} {r['pnl_pct']:>+6.1f}% {r['filter_score']:>6.1f} {r['would_enter']:<14} {r.get('rsi',0):>5.0f} {r.get('macd',0):>5.0f} {r.get('vol_spike',0):>5.0f} {r.get('ma_align',0):>5.0f} {r.get('momentum',0):>5.0f}")

    # --- Summary ---
    scored = [r for r in results if r['filter_score'] >= 0]
    passed = [r for r in scored if r['would_enter'] == 'YES']
    filtered = [r for r in scored if r['would_enter'] == 'FILTERED OUT']
    errors = [r for r in results if r['filter_score'] < 0]

    print()
    print("=" * 110)
    print("  SUMMARY")
    print("=" * 110)
    print(f"  Total open trades:     {len(results)}")
    print(f"  Successfully scored:   {len(scored)}")
    print(f"  Passed filter (>=50):  {len(passed)}")
    print(f"  Filtered out (<50):    {len(filtered)}")
    print(f"  Errors/no data:        {len(errors)}")
    print()

    if passed:
        avg_pnl_passed = np.mean([r['pnl_pct'] for r in passed])
        wins_passed = sum(1 for r in passed if r['pnl_pct'] > 0)
        print(f"  PASSED filter — avg P&L: {avg_pnl_passed:+.2f}%, wins: {wins_passed}/{len(passed)} ({wins_passed/len(passed)*100:.0f}%)")
    if filtered:
        avg_pnl_filtered = np.mean([r['pnl_pct'] for r in filtered])
        wins_filtered = sum(1 for r in filtered if r['pnl_pct'] > 0)
        print(f"  FILTERED OUT — avg P&L: {avg_pnl_filtered:+.2f}%, wins: {wins_filtered}/{len(filtered)} ({wins_filtered/len(filtered)*100:.0f}%)")

    if passed and filtered:
        print()
        print("  KEY QUESTION: Did the filter correctly keep winners and remove losers?")
        print()

        # Confusion matrix
        tp = sum(1 for r in passed if r['pnl_pct'] > 0)      # kept winners
        fn = sum(1 for r in filtered if r['pnl_pct'] > 0)    # removed winners (bad!)
        fp = sum(1 for r in passed if r['pnl_pct'] <= 0)     # kept losers (bad!)
        tn = sum(1 for r in filtered if r['pnl_pct'] <= 0)   # removed losers (good!)

        print(f"  Confusion Matrix (winner = P&L > 0):")
        print(f"                    Kept (pass)   Filtered (fail)")
        print(f"  Winners (P&L>0)   {tp:>10}    {fn:>10}")
        print(f"  Losers  (P&L<=0)  {fp:>10}    {tn:>10}")
        print()
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        print(f"  Precision (kept winners / all kept):     {precision:.0f}%")
        print(f"  Recall (kept winners / all winners):     {recall:.0f}%")
        print()

        if recall < 60:
            print(f"  >>> WARNING: Filter removed {fn} of {tp+fn} winners ({100-recall:.0f}%). May be too aggressive.")
        elif precision > 70:
            print(f"  >>> GOOD: Filter kept mostly winners ({precision:.0f}% precision).")
        else:
            print(f"  >>> MIXED: Filter has {precision:.0f}% precision, {recall:.0f}% recall.")

    # --- Also score waiting breakout picks ---
    if len(waiting) > 0:
        print()
        print("=" * 110)
        print("  WAITING FOR BREAKOUT — Current Entry Filter Score")
        print("=" * 110)
        print()
        print(f"  {'Symbol':<16} {'Pattern':<22} {'Breakout':>10} {'Now':>10} {'Score':>6} {'Verdict':<14}")
        print("  " + "-" * 90)

        for idx, row in waiting.iterrows():
            sym = row['symbol']
            breakout = float(row.get('breakout_level', 0))
            if breakout == 0:
                breakout = float(row.get('entry_price', 0))
            current_price = float(row['current_price'])

            try:
                df = _fetch_nse(sym.replace('.NS', ''), days=200)
                if df is None or len(df) < 60:
                    print(f"  {sym:<16} {row.get('pattern',''):<22} {breakout:>10.2f} {current_price:>10.2f} {'N/A':>6} NO DATA")
                    continue

                score, details = score_entry(df, breakout)
                verdict = 'WOULD ENTER' if score >= THRESHOLD else 'WAIT'
                print(f"  {sym:<16} {row.get('pattern',''):<22} {breakout:>10.2f} {current_price:>10.2f} {score:>6.1f} {verdict}")
            except Exception as e:
                print(f"  {sym:<16} {row.get('pattern',''):<22} {breakout:>10.2f} {current_price:>10.2f} {'ERR':>6} {str(e)[:30]}")

    # Save results
    df_out = pd.DataFrame(results)
    df_out.to_csv('forward_test_results.csv', index=False)
    print()
    print("  Saved forward_test_results.csv")


if __name__ == "__main__":
    main()
