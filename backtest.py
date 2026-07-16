"""
Backtest entry point v3.

Usage:
  python backtest.py --symbols RELIANCE.NS TCS.NS INFY.NS
  python backtest.py --stocks backbone50.txt --years 2 --min-score 50
  python backtest.py --symbols HDFCBANK.NS --years 1 --scan-every 3
  python backtest.py --stocks backbone50.txt --no-atr   # use original SL (v2 mode)
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtester.engine import backtest_portfolio
from backtester.report import generate_report


def load_stocks(filepath):
    try:
        with open(filepath) as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Swing trading strategy backtester v3")
    parser.add_argument("--stocks", default="backbone50.txt", help="Path to stock symbols file")
    parser.add_argument("--symbols", nargs="+", help="Override with specific symbols")
    parser.add_argument("--years", type=int, default=2, help="Years of history (default: 2)")
    parser.add_argument("--min-score", type=float, default=50, help="Min pattern score (default: 50)")
    parser.add_argument("--scan-every", type=int, default=5, help="Scan every N bars (default: 5)")
    parser.add_argument("--output", default="backtest_results.csv", help="Output CSV filename")
    parser.add_argument("--no-atr", action="store_true", help="Use original SL (v2 mode) instead of ATR")
    args = parser.parse_args()

    if args.symbols:
        symbols = args.symbols
    else:
        symbols = load_stocks(args.stocks)
        if not symbols:
            print("No symbols to backtest. Use --symbols RELIANCE.NS TCS.NS or provide a stocks.txt file.")
            sys.exit(1)

    print(f"\nBacktesting {len(symbols)} symbol(s) | {args.years}yr history | "
          f"min_score={args.min_score} | scan_every={args.scan_every}d | "
          f"SL: {'original' if args.no_atr else 'ATR'}\n")

    trades = backtest_portfolio(
        symbols,
        years=args.years,
        min_score=args.min_score,
        scan_every=args.scan_every,
        atr_stop=not args.no_atr,
    )

    generate_report(trades, output_csv=args.output)


if __name__ == "__main__":
    main()
