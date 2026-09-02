"""
Run baseline vs entry-filter backtest and compare.

Usage:
  python run_comparison.py --stocks nifty200.txt --years 2 --min-score 50
  python run_comparison.py --stocks backbone50.txt --years 2 --filter-threshold 50
"""
import sys, os, argparse, time
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtester.engine import backtest_portfolio as baseline_bt
from backtester.engine_with_filter import backtest_portfolio as filter_bt
from backtester.report import generate_report


def load_stocks(filepath):
    with open(filepath) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def calc_stats(trades):
    """Calculate summary stats from trade list."""
    if not trades:
        return {"trades": 0}
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

    # Max drawdown (approximate — sequential sum)
    cum = df['pnl_pct'].cumsum()
    running_max = cum.expanding().max()
    dd = cum - running_max
    max_dd = dd.min()

    # Exit reason breakdown
    exits = df['exit_reason'].value_counts().to_dict()

    # Pattern breakdown
    pats = df['pattern'].value_counts().to_dict()

    return {
        "trades": len(df),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "pf": round(pf, 2),
        "max_dd": round(max_dd, 2),
        "avg_days": round(df['days_held'].mean(), 1),
        "exit_reasons": exits,
        "top_patterns": dict(list(pats.items())[:5]),
    }


def print_comparison(baseline_stats, filter_stats, threshold):
    print()
    print("=" * 90)
    print("  V3.1 BASELINE  vs  V3.1 + ENTRY CONFIRMATION FILTER")
    print("=" * 90)
    print()
    print(f"  {'Metric':<25}  {'Baseline':>15}  {'+Filter':>15}  {'Delta':>15}")
    print("  " + "-" * 75)

    metrics = [
        ("Trades",        "trades",       "d",  False),
        ("Wins",          "wins",         "d",  False),
        ("Losses",        "losses",       "d",  False),
        ("Win rate %",    "win_rate",     ".1f", True),
        ("Avg win %",     "avg_win",      ".2f", True),
        ("Avg loss %",    "avg_loss",     ".2f", True),
        ("Expectancy %",  "expectancy",   ".2f", True),
        ("Profit factor", "pf",           ".2f", True),
        ("Max drawdown %","max_dd",       ".2f", True),
        ("Avg days held", "avg_days",     ".1f", True),
    ]

    for label, key, fmt, show_delta in metrics:
        b = baseline_stats.get(key, 0)
        f = filter_stats.get(key, 0)
        if fmt == "d":
            b_str = f"{int(b):>15}"
            f_str = f"{int(f):>15}"
        else:
            b_str = f"{b:>15{fmt}}"
            f_str = f"{f:>15{fmt}}"
        if show_delta:
            delta = f - b
            sign = "+" if delta >= 0 else ""
            d_str = f"{sign}{delta:>14{fmt}}"
        else:
            delta = f - b
            sign = "+" if delta >= 0 else ""
            d_str = f"{sign}{int(delta):>14}"
        print(f"  {label:<25}  {b_str}  {f_str}  {d_str}")

    # Exit reasons
    print()
    print("  EXIT REASONS")
    print("  " + "-" * 75)
    all_reasons = set(list(baseline_stats.get('exit_reasons', {}).keys()) +
                      list(filter_stats.get('exit_reasons', {}).keys()))
    for reason in sorted(all_reasons):
        b = baseline_stats.get('exit_reasons', {}).get(reason, 0)
        f = filter_stats.get('exit_reasons', {}).get(reason, 0)
        print(f"  {reason:<25}  {b:>15}  {f:>15}  {f-b:>+15}")

    # Top patterns
    print()
    print("  TOP PATTERNS (baseline)")
    print("  " + "-" * 75)
    for pat, count in baseline_stats.get('top_patterns', {}).items():
        f_count = filter_stats.get('top_patterns', {}).get(pat, 0)
        print(f"  {pat:<25}  {count:>15}  {f_count:>15}  {f_count-count:>+15}")

    # Verdict
    print()
    print("=" * 90)
    print("  VERDICT")
    print("=" * 90)
    exp_delta = filter_stats.get('expectancy', 0) - baseline_stats.get('expectancy', 0)
    wr_delta = filter_stats.get('win_rate', 0) - baseline_stats.get('win_rate', 0)
    pf_delta = filter_stats.get('pf', 0) - baseline_stats.get('pf', 0)
    trade_delta = filter_stats.get('trades', 0) - baseline_stats.get('trades', 0)

    if exp_delta > 0.3 and wr_delta > 0:
        verdict = "FILTER HELPS — expectancy and win rate both improved"
        recommend = "RECOMMEND MERGE"
    elif exp_delta > 0.2:
        verdict = "FILTER HELPS MARGINALLY — expectancy up but check trade count"
        recommend = "CONSIDER MERGE (test more thresholds)"
    elif exp_delta > 0:
        verdict = "FILTER NEUTRAL — slight improvement, may be noise"
        recommend = "DO NOT MERGE YET"
    else:
        verdict = "FILTER HURTS — expectancy dropped"
        recommend = "DO NOT MERGE"

    print(f"  Expectancy delta:  {exp_delta:+.2f}%")
    print(f"  Win rate delta:    {wr_delta:+.1f}%")
    print(f"  Profit factor delta: {pf_delta:+.2f}")
    print(f"  Trade count delta: {trade_delta:+d} (filter removed {-trade_delta if trade_delta < 0 else 0} trades)")
    print()
    print(f"  >>> {verdict}")
    print(f"  >>> {recommend}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Compare baseline vs entry-filter backtest")
    parser.add_argument("--stocks", default="nifty200.txt", help="Stock symbols file")
    parser.add_argument("--years", type=int, default=2, help="Years of history")
    parser.add_argument("--min-score", type=float, default=50, help="Min pattern score")
    parser.add_argument("--scan-every", type=int, default=5, help="Scan every N bars")
    parser.add_argument("--filter-threshold", type=float, default=50.0,
                        help="Entry confirmation min score (default 50)")
    parser.add_argument("--save-csv", action="store_true", help="Save trade CSVs for both runs")
    args = parser.parse_args()

    symbols = load_stocks(args.stocks)
    if not symbols:
        print(f"No symbols found in {args.stocks}")
        sys.exit(1)

    print(f"\nStocks: {len(symbols)} | Years: {args.years} | Min score: {args.min_score}")
    print(f"Filter threshold: {args.filter_threshold}")
    print()

    # --- BASELINE ---
    print("=" * 90)
    print("  PHASE 1: BASELINE (v3.1, no entry filter)")
    print("=" * 90)
    t0 = time.time()
    baseline_trades = baseline_bt(
        symbols, years=args.years, min_score=args.min_score,
        scan_every=args.scan_every, atr_stop=True
    )
    t1 = time.time()
    print(f"\n  Baseline: {len(baseline_trades)} trades in {t1-t0:.0f}s")
    baseline_stats = calc_stats(baseline_trades)

    if args.save_csv:
        pd.DataFrame(baseline_trades).to_csv("baseline_trades.csv", index=False)
        print("  Saved baseline_trades.csv")

    # --- WITH FILTER ---
    print()
    print("=" * 90)
    print(f"  PHASE 2: V3.1 + ENTRY FILTER (threshold={args.filter_threshold})")
    print("=" * 90)
    t0 = time.time()
    filter_trades = filter_bt(
        symbols, years=args.years, min_score=args.min_score,
        scan_every=args.scan_every, atr_stop=True,
        entry_filter_threshold=args.filter_threshold
    )
    t1 = time.time()
    print(f"\n  Filtered: {len(filter_trades)} trades in {t1-t0:.0f}s")
    filter_stats = calc_stats(filter_trades)

    if args.save_csv:
        pd.DataFrame(filter_trades).to_csv("filter_trades.csv", index=False)
        print("  Saved filter_trades.csv")

    # --- COMPARISON ---
    print_comparison(baseline_stats, filter_stats, args.filter_threshold)


if __name__ == "__main__":
    main()
