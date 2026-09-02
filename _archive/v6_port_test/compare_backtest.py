"""
Compare v3 vs v2 backtest performance on the same stocks.

Runs both backtest modes (ATR stops = v3, original stops = v2)
on the same universe and produces a side-by-side comparison report.

Usage:
  python compare_backtest.py --stocks backbone50.txt --years 2
  python compare_backtest.py --symbols RELIANCE.NS TCS.NS --years 1
"""
import os, sys, argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtester.engine import backtest_portfolio
from backtester.report import generate_report


def load_stocks(filepath):
    try:
        with open(filepath) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return []


def _summary(trades, label):
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
    gross_profit = df.loc[df["pnl_pct"] > 0, "pnl_pct"].sum()
    gross_loss = abs(df.loc[df["pnl_pct"] < 0, "pnl_pct"].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    equity = (1 + df["pnl_pct"] / 100).cumprod()
    dd = ((equity - equity.cummax()) / equity.cummax() * 100).min()
    return {
        "label": label,
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "profit_factor": round(pf, 2),
        "max_drawdown": round(dd, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Compare v3 vs v2 backtest")
    parser.add_argument("--stocks", default="backbone50.txt")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--min-score", type=float, default=50)
    parser.add_argument("--scan-every", type=int, default=5)
    args = parser.parse_args()

    if args.symbols:
        symbols = args.symbols
    else:
        symbols = load_stocks(args.stocks)
        if not symbols:
            print("No symbols. Use --symbols or provide a stocks file.")
            sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  V3 vs V2 BACKTEST COMPARISON")
    print(f"  {len(symbols)} stocks | {args.years} years | min_score={args.min_score}")
    print(f"{'='*70}")

    # --- Run v3 (ATR stops) ---
    print(f"\n[1/2] Running v3 backtest (ATR stops, trailing after T1)...")
    trades_v3 = backtest_portfolio(symbols, years=args.years, min_score=args.min_score,
                                   scan_every=args.scan_every, atr_stop=True)
    df_v3 = pd.DataFrame(trades_v3) if trades_v3 else pd.DataFrame()
    if not df_v3.empty:
        df_v3.to_csv("results/backtest_v3.csv", index=False)

    # --- Run v2 (original stops, no trailing) ---
    print(f"\n[2/2] Running v2 backtest (original stops, no trailing)...")
    trades_v2 = backtest_portfolio(symbols, years=args.years, min_score=args.min_score,
                                   scan_every=args.scan_every, atr_stop=False)
    df_v2 = pd.DataFrame(trades_v2) if trades_v2 else pd.DataFrame()
    if not df_v2.empty:
        df_v2.to_csv("results/backtest_v2.csv", index=False)

    # --- Comparison ---
    s_v3 = _summary(trades_v3, "v3 (ATR + trailing)")
    s_v2 = _summary(trades_v2, "v2 (original)")

    print(f"\n{'='*70}")
    print(f"  COMPARISON REPORT")
    print(f"{'='*70}")
    print(f"  {'Metric':<20} {'v3 (ATR+trail)':>16} {'v2 (original)':>16} {'Delta':>10}")
    print(f"  {'-'*65}")
    for key in ["trades", "wins", "losses", "win_rate", "avg_win", "avg_loss",
                "expectancy", "profit_factor", "max_drawdown"]:
        v3_val = s_v3.get(key, 0)
        v2_val = s_v2.get(key, 0)
        delta = ""
        if isinstance(v3_val, (int, float)) and isinstance(v2_val, (int, float)):
            d = v3_val - v2_val
            delta = f"{d:+.2f}" if isinstance(d, float) else f"{d:+d}"
        print(f"  {key:<20} {str(v3_val):>16} {str(v2_val):>16} {delta:>10}")

    # --- By pattern comparison ---
    if not df_v3.empty and not df_v2.empty:
        print(f"\n{'='*70}")
        print(f"  BY PATTERN — v3 vs v2")
        print(f"{'='*70}")
        pat_v3 = df_v3.groupby("pattern").agg(
            trades_v3=("pnl_pct", "count"),
            win_rate_v3=("result", lambda x: f"{(x=='WIN').mean()*100:.1f}%"),
            avg_pnl_v3=("pnl_pct", lambda x: f"{x.mean():.2f}%"),
        ).reset_index()
        pat_v2 = df_v2.groupby("pattern").agg(
            trades_v2=("pnl_pct", "count"),
            win_rate_v2=("result", lambda x: f"{(x=='WIN').mean()*100:.1f}%"),
            avg_pnl_v2=("pnl_pct", lambda x: f"{x.mean():.2f}%"),
        ).reset_index()
        merged = pat_v3.merge(pat_v2, on="pattern", how="outer").fillna("-")
        print(merged.to_string(index=False))

    # --- By exit reason ---
    if not df_v3.empty:
        print(f"\n{'='*70}")
        print(f"  V3 EXIT REASONS")
        print(f"{'='*70}")
        ex = df_v3.groupby("exit_reason").agg(
            trades=("pnl_pct", "count"),
            avg_pnl=("pnl_pct", lambda x: f"{x.mean():.2f}%"),
        ).reset_index()
        print(ex.to_string(index=False))

    print(f"\n  CSVs saved: results/backtest_v3.csv, results/backtest_v2.csv")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
