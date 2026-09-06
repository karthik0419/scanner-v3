"""
SwingIQ Weekly Performance Tracker

Tracks the performance of SwingIQ picks from Friday's scan over the
following week (Monday to Friday). On Friday at 6:00 PM, sends a
Telegram alert to the SwingIQ channel with the weekly performance.

Flow:
  1. Friday: SwingIQ scan produces picks (v3_YYYY-MM-DD.csv)
  2. Monday-Friday: Those picks are tracked
  3. Next Friday 6 PM: This script runs and sends the weekly performance

Usage:
  python weekly_performance.py                    # auto-detect last Friday's scan
  python weekly_performance.py --scan-date 2026-08-29   # specific Friday
  python weekly_performance.py --weeks 4          # show last 4 weeks (no Telegram)
  python weekly_performance.py --send             # send Telegram alert
  python weekly_performance.py --env-file .env.swingiq  # SwingIQ channel
"""
import os
import sys
import argparse
import pandas as pd
import yfinance as yf
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_notify import _get_credentials, send_telegram

RESULTS_DIR = Path(__file__).parent / "results"
LOG_DIR = Path(__file__).parent / "logs"


def find_friday_scan(scan_date=None):
    """Find the Friday scan CSV. If scan_date given, use that. Otherwise,
    find the most recent Friday that has a scan CSV."""
    if scan_date:
        fname = f"v3_{scan_date}.csv"
        path = RESULTS_DIR / fname
        if path.exists():
            return scan_date, path
        raise FileNotFoundError(f"No scan CSV for {scan_date}: {path}")

    # Walk backwards from today to find the most recent Friday
    today = date.today()
    # If today is Friday, use today. Otherwise use the previous Friday.
    days_since_friday = (today.weekday() - 4) % 7
    friday = today - timedelta(days=days_since_friday)

    # Search backwards up to 14 days for a scan CSV
    for i in range(14):
        d = friday - timedelta(days=i)
        fname = f"v3_{d.isoformat()}.csv"
        path = RESULTS_DIR / fname
        if path.exists():
            return d.isoformat(), path

    raise FileNotFoundError("No Friday scan CSV found in the last 2 weeks")


def find_next_friday(scan_date_str):
    """Get the next Friday after the scan date."""
    d = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
    days_to_friday = (4 - d.weekday()) % 7
    if days_to_friday == 0:
        days_to_friday = 7  # next Friday, not same day
    return d + timedelta(days=days_to_friday)


def fetch_close_prices(symbols, target_date):
    """Fetch closing prices for a list of symbols on or before target_date.
    Uses yfinance. Returns dict {symbol: close_price}."""
    prices = {}
    tickers_str = " ".join(symbols)
    start = target_date - timedelta(days=5)
    end = target_date + timedelta(days=1)

    try:
        data = yf.download(tickers_str, start=start, end=end, progress=False,
                           group_by='column', auto_adjust=False)

        if len(symbols) == 1:
            # Single ticker — columns are flat (Close, High, Low, etc.)
            if len(data) > 0 and 'Close' in data.columns:
                s = data['Close'].dropna()
                if len(s) > 0:
                    prices[symbols[0]] = float(s.iloc[-1])
        else:
            # Multiple tickers — columns are MultiIndex (field, ticker)
            if isinstance(data.columns, pd.MultiIndex):
                close_df = data['Close']
            elif 'Close' in data.columns:
                close_df = data['Close']
            else:
                close_df = data

            for sym in symbols:
                try:
                    if sym in close_df.columns:
                        s = close_df[sym].dropna()
                        if len(s) > 0:
                            prices[sym] = float(s.iloc[-1])
                except Exception:
                    pass
    except Exception as e:
        print(f"  [ERROR] yfinance download failed: {e}")

    return prices


def calculate_weekly_performance(scan_date_str, scan_csv_path, end_date=None):
    """Calculate weekly performance for picks from a Friday scan.

    Returns a DataFrame with columns:
      symbol, pattern, status, friday_close, current_close, pct_change, status_label
    """
    # Load the scan picks
    picks = pd.read_csv(scan_csv_path)
    if 'symbol' not in picks.columns:
        raise ValueError(f"Invalid scan CSV: no 'symbol' column in {scan_csv_path}")

    # Filter to tradeable picks (BREAKOUT + NEAR, skip WATCH)
    tradeable = picks[picks['status'].isin(['BREAKOUT', 'NEAR'])].copy()
    if len(tradeable) == 0:
        tradeable = picks.copy()  # fallback: use all

    symbols = tradeable['symbol'].tolist()
    friday_closes = dict(zip(tradeable['symbol'], tradeable['cmp']))

    # Determine the end date (next Friday)
    if end_date is None:
        end_date = find_next_friday(scan_date_str)
    elif isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    print(f"  Scan date: {scan_date_str} ({len(tradeable)} tradeable picks)")
    print(f"  Tracking to: {end_date}")

    # Fetch current/close prices
    print(f"  Fetching prices for {len(symbols)} symbols...")
    current_prices = fetch_close_prices(symbols, end_date)

    # Build results
    results = []
    for _, row in tradeable.iterrows():
        sym = row['symbol']
        fri_close = float(row['cmp'])
        curr_close = current_prices.get(sym)
        if curr_close is None or curr_close <= 0:
            pct_change = None
            status_label = "NO DATA"
        else:
            pct_change = ((curr_close - fri_close) / fri_close) * 100
            if pct_change > 0:
                status_label = "PROFIT"
            elif pct_change < 0:
                status_label = "LOSS"
            else:
                status_label = "FLAT"

        results.append({
            'symbol': sym,
            'pattern': row.get('pattern', ''),
            'scan_status': row.get('status', ''),
            'friday_close': fri_close,
            'current_close': curr_close,
            'pct_change': pct_change,
            'status_label': status_label,
            'sector': row.get('sector', ''),
        })

    return pd.DataFrame(results), end_date


def summarize_performance(df, scan_date, end_date):
    """Build a summary of the weekly performance."""
    valid = df[df['pct_change'].notna()]
    total = len(df)
    valid_count = len(valid)

    if valid_count == 0:
        return {
            'scan_date': scan_date,
            'end_date': end_date,
            'total_picks': total,
            'valid': 0,
            'winners': 0,
            'losers': 0,
            'flat': 0,
            'win_rate': 0,
            'avg_change': 0,
            'median_change': 0,
            'best_pick': 'N/A',
            'best_pct': 0,
            'worst_pick': 'N/A',
            'worst_pct': 0,
            'sum_change': 0,
            'top3': [],
            'bottom3': [],
        }

    winners = valid[valid['pct_change'] > 0]
    losers = valid[valid['pct_change'] < 0]
    flat = valid[valid['pct_change'] == 0]

    best_row = valid.loc[valid['pct_change'].idxmax()]
    worst_row = valid.loc[valid['pct_change'].idxmin()]

    return {
        'scan_date': scan_date,
        'end_date': end_date,
        'total_picks': total,
        'valid': valid_count,
        'winners': len(winners),
        'losers': len(losers),
        'flat': len(flat),
        'win_rate': len(winners) / valid_count * 100 if valid_count > 0 else 0,
        'avg_change': valid['pct_change'].mean(),
        'median_change': valid['pct_change'].median(),
        'best_pick': best_row['symbol'],
        'best_pct': best_row['pct_change'],
        'worst_pick': worst_row['symbol'],
        'worst_pct': worst_row['pct_change'],
        'sum_change': valid['pct_change'].sum(),
        'top3': valid.nlargest(3, 'pct_change')[['symbol', 'pct_change', 'pattern']].values.tolist(),
        'bottom3': valid.nsmallest(3, 'pct_change')[['symbol', 'pct_change', 'pattern']].values.tolist(),
    }


def build_telegram_message(summary, df, scan_date, end_date):
    """Build the Telegram message for weekly performance."""
    lines = [
        f"📊 <b>SwingIQ Weekly Performance Report</b>",
        f"📅 Scan: {scan_date} → Track: {end_date}",
        f"📦 Picks: {summary['total_picks']} | Tracked: {summary['valid']}",
        "",
    ]

    if summary['valid'] == 0:
        lines.append("⚠️ No price data available for this week.")
        return "\n".join(lines)

    # Overall stats
    wr_emoji = "🟢" if summary['win_rate'] >= 50 else "🔴"
    avg_emoji = "🟢" if summary['avg_change'] > 0 else "🔴"
    lines.extend([
        f"{wr_emoji} <b>Win Rate:</b> {summary['win_rate']:.1f}% "
        f"({summary['winners']}W / {summary['losers']}L)",
        f"{avg_emoji} <b>Avg Change:</b> {summary['avg_change']:+.2f}%",
        f"📈 <b>Median:</b> {summary['median_change']:+.2f}%",
        f"💰 <b>Sum Change:</b> {summary['sum_change']:+.2f}%",
        "",
    ])

    # Best and worst
    lines.append(f"🏆 <b>Best:</b> {summary['best_pick']} ({summary['best_pct']:+.2f}%)")
    lines.append(f"💀 <b>Worst:</b> {summary['worst_pick']} ({summary['worst_pct']:+.2f}%)")
    lines.append("")

    # Top 3
    if summary.get('top3'):
        lines.append("🟢 <b>TOP 3</b>")
        for sym, pct, pat in summary['top3']:
            lines.append(f"  {sym} → {pct:+.2f}% ({pat})")
        lines.append("")

    # Bottom 3
    if summary.get('bottom3'):
        lines.append("🔴 <b>BOTTOM 3</b>")
        for sym, pct, pat in summary['bottom3']:
            lines.append(f"  {sym} → {pct:+.2f}% ({pat})")
        lines.append("")

    # All picks detail (if not too many)
    valid = df[df['pct_change'].notna()].sort_values('pct_change', ascending=False)
    if len(valid) <= 15:
        lines.append("📋 <b>ALL PICKS</b>")
        for _, r in valid.iterrows():
            emoji = "🟢" if r['pct_change'] > 0 else "🔴" if r['pct_change'] < 0 else "⚪"
            lines.append(f"  {emoji} {r['symbol']} → {r['pct_change']:+.2f}% ({r['pattern']})")
        lines.append("")

    lines.append("🤖 SwingIQ Weekly Tracker | Friday 6 PM")

    return "\n".join(lines)


def run_weekly_performance(scan_date=None, end_date=None, send_telegram_alert=False,
                           env_file=None, verbose=True):
    """Main function to run weekly performance tracking."""
    # Find the scan
    found_date, scan_path = find_friday_scan(scan_date)
    if verbose:
        print(f"\n{'='*60}")
        print(f"  SwingIQ Weekly Performance Tracker")
        print(f"{'='*60}")

    # Calculate performance
    df, actual_end_date = calculate_weekly_performance(found_date, scan_path, end_date)

    # Summarize
    summary = summarize_performance(df, found_date, actual_end_date)

    if verbose:
        print(f"\n  Results:")
        print(f"    Winners: {summary['winners']} | Losers: {summary['losers']}")
        print(f"    Win Rate: {summary['win_rate']:.1f}%")
        print(f"    Avg Change: {summary['avg_change']:+.2f}%")
        print(f"    Best: {summary['best_pick']} ({summary['best_pct']:+.2f}%)")
        print(f"    Worst: {summary['worst_pick']} ({summary['worst_pct']:+.2f}%)")

    # Build message
    msg = build_telegram_message(summary, df, found_date, actual_end_date)

    if verbose:
        print(f"\n{'='*60}")
        print(msg)
        print(f"{'='*60}")

    # Send Telegram
    if send_telegram_alert:
        token, chat_id = _get_credentials(env_file)
        if token and chat_id:
            ok = send_telegram(token, chat_id, msg)
            if ok:
                print("\n[ALERT] Telegram message sent to SwingIQ.")
            else:
                print("\n[ALERT] Telegram send FAILED.")
        else:
            print("\n[ALERT] No Telegram credentials — message printed above only.")

    # Save to log
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"weekly_perf_{found_date}.csv"
    df.to_csv(log_path, index=False)
    if verbose:
        print(f"\n  Saved: {log_path}")

    return summary, df


def run_multi_week(weeks=4, verbose=True):
    """Run performance for the last N weeks and print a summary table."""
    today = date.today()
    # Find the most recent Friday
    days_since_friday = (today.weekday() - 4) % 7
    latest_friday = today - timedelta(days=days_since_friday)

    print(f"\n{'='*70}")
    print(f"  SwingIQ — Last {weeks} Weeks Performance Summary")
    print(f"{'='*70}\n")

    all_summaries = []
    week_fridays = []

    # Collect the last N Fridays (going back 7 days each time)
    for i in range(weeks):
        # Each week: scan Friday is 7*(i+1) days before latest_friday
        # End date is 7*i days before latest_friday
        scan_fri = latest_friday - timedelta(days=7 * (i + 1))
        end_fri = latest_friday - timedelta(days=7 * i)
        week_fridays.append((scan_fri, end_fri))

    # Process in chronological order (oldest first)
    week_fridays.reverse()

    for scan_fri, end_fri in week_fridays:
        scan_str = scan_fri.isoformat()
        end_str = end_fri.isoformat()
        fname = f"v3_{scan_str}.csv"
        path = RESULTS_DIR / fname

        if not path.exists():
            # Try nearby dates (±1-2 days for holidays)
            found = False
            for offset in [1, -1, 2, -2, 3, -3]:
                alt_date = scan_fri + timedelta(days=offset)
                alt_str = alt_date.isoformat()
                alt_path = RESULTS_DIR / f"v3_{alt_str}.csv"
                if alt_path.exists():
                    scan_str = alt_str
                    path = alt_path
                    found = True
                    break
            if not found:
                print(f"  Week of {scan_str}: NO SCAN DATA (skipping)")
                continue

        print(f"  Week of {scan_str} → {end_str}:")
        try:
            summary, df = run_weekly_performance(
                scan_date=scan_str,
                end_date=end_str,
                send_telegram_alert=False,
                verbose=False
            )
            all_summaries.append(summary)
            print(f"    Picks: {summary['total_picks']} | Tracked: {summary['valid']}")
            print(f"    Win Rate: {summary['win_rate']:.1f}% ({summary['winners']}W / {summary['losers']}L)")
            print(f"    Avg: {summary['avg_change']:+.2f}% | Median: {summary['median_change']:+.2f}%")
            print(f"    Best: {summary['best_pick']} ({summary['best_pct']:+.2f}%)")
            print(f"    Worst: {summary['worst_pick']} ({summary['worst_pct']:+.2f}%)")
            print()
        except Exception as e:
            print(f"    ERROR: {e}\n")

    # Summary table
    if all_summaries:
        print(f"\n{'='*70}")
        print(f"  SUMMARY TABLE — Last {len(all_summaries)} Weeks")
        print(f"{'='*70}")
        print(f"  {'Scan Date':<12} {'Picks':>5} {'WR':>6} {'Avg%':>8} {'Best':>15} {'Worst':>15}")
        print(f"  {'-'*12} {'-'*5} {'-'*6} {'-'*8} {'-'*15} {'-'*15}")
        for s in all_summaries:
            best_str = f"{s['best_pick'][:12]} {s['best_pct']:+.1f}%"
            worst_str = f"{s['worst_pick'][:12]} {s['worst_pct']:+.1f}%"
            print(f"  {s['scan_date']:<12} {s['total_picks']:>5} {s['win_rate']:>5.1f}% {s['avg_change']:>+7.2f}% {best_str:>15} {worst_str:>15}")

        # Overall aggregate
        total_winners = sum(s['winners'] for s in all_summaries)
        total_losers = sum(s['losers'] for s in all_summaries)
        total_valid = sum(s['valid'] for s in all_summaries)
        all_avgs = [s['avg_change'] for s in all_summaries]
        avg_of_avgs = sum(all_avgs) / len(all_avgs) if all_avgs else 0
        overall_wr = total_winners / total_valid * 100 if total_valid > 0 else 0

        print(f"  {'-'*12} {'-'*5} {'-'*6} {'-'*8} {'-'*15} {'-'*15}")
        print(f"  {'OVERALL':<12} {total_valid:>5} {overall_wr:>5.1f}% {avg_of_avgs:>+7.2f}%")
        print(f"{'='*70}")

    return all_summaries


def main():
    parser = argparse.ArgumentParser(description="SwingIQ Weekly Performance Tracker")
    parser.add_argument("--scan-date", default=None, help="Friday scan date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="End date for tracking (YYYY-MM-DD)")
    parser.add_argument("--weeks", type=int, default=None, help="Show last N weeks summary")
    parser.add_argument("--send", action="store_true", help="Send Telegram alert")
    parser.add_argument("--env-file", default=None, help="Env file for Telegram credentials")
    args = parser.parse_args()

    if args.weeks:
        run_multi_week(weeks=args.weeks, verbose=True)
    else:
        run_weekly_performance(
            scan_date=args.scan_date,
            end_date=args.end_date,
            send_telegram_alert=args.send,
            env_file=args.env_file,
            verbose=True
        )


if __name__ == "__main__":
    main()
