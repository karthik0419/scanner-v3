"""Generate today's performance report from paper tracker."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import yfinance as yf
from datetime import datetime
from telegram_notify import send_telegram, _get_credentials

df = pd.read_csv('results/paper_tracker.csv')
print(f"Total picks in tracker: {len(df)}")
print(f"Scan dates: {df['scan_date'].unique()}")
print()

# Fetch current prices for all
print("Fetching current prices...")
symbols = df['symbol'].unique().tolist()
current_prices = {}
for sym in symbols:
    try:
        hist = yf.Ticker(sym).history(period='5d')
        if hist is not None and len(hist) > 0:
            current_prices[sym] = float(hist['Close'].iloc[-1])
    except:
        pass

df['live_price'] = df['symbol'].map(current_prices)

# Calculate P&L for each pick
# For OPEN trades: (live_price - entry_price) / entry_price * 100
# For WAITING_BREAKOUT: not entered yet, show CMP vs breakout
# For WIN_T1/WIN_T2/LOSS/TIME_EXIT: use exit_price

def calc_pnl(row):
    status = row.get('current_status', row.get('status', ''))
    if pd.isna(status) or status == '':
        status = row.get('status_at_scan', 'UNKNOWN')

    if status in ['WIN_T1', 'WIN_T2', 'LOSS', 'TIME_EXIT', 'RE_ENTERED']:
        exit_p = row.get('exit_price')
        entry_p = row.get('entry_price')
        if pd.notna(exit_p) and pd.notna(entry_p) and entry_p > 0:
            return round((exit_p - entry_p) / entry_p * 100, 2)
        return 0
    elif status == 'OPEN':
        entry_p = row.get('entry_price')
        live = row.get('live_price')
        if pd.notna(entry_p) and pd.notna(live) and entry_p > 0:
            return round((live - entry_p) / entry_p * 100, 2)
        return 0
    elif status == 'WAITING_BREAKOUT':
        # Not entered — show how far from breakout
        breakout = row.get('breakout_level')
        live = row.get('live_price')
        if pd.notna(breakout) and pd.notna(live) and breakout > 0:
            return round((live - breakout) / breakout * 100, 2)
        return 0
    return 0

df['pnl_pct'] = df.apply(calc_pnl, axis=1)

# Categorize
open_trades = df[df['current_status'] == 'OPEN']
waiting = df[df['current_status'] == 'WAITING_BREAKOUT']
wins = df[df['current_status'].isin(['WIN_T1', 'WIN_T2'])]
losses = df[df['current_status'] == 'LOSS']
time_exits = df[df['current_status'] == 'TIME_EXIT']

print(f"\nOPEN trades: {len(open_trades)}")
print(f"WAITING_BREAKOUT: {len(waiting)}")
print(f"WINS (T1/T2): {len(wins)}")
print(f"LOSSES: {len(losses)}")
print(f"TIME_EXIT: {len(time_exits)}")
print()

# Open trades performance
print("=" * 80)
print("  OPEN TRADES (entered, active)")
print("=" * 80)
print(f"  {'Symbol':>16s}  {'Pattern':>20s}  {'Entry':>8s}  {'Live':>8s}  {'P&L%':>7s}  {'Days':>5s}  {'SL':>8s}  {'T1':>8s}")
for _, r in open_trades.sort_values('pnl_pct', ascending=False).iterrows():
    print(f"  {r['symbol']:>16s}  {r['pattern']:>20s}  Rs {r['entry_price']:>6.2f}  Rs {r['live_price']:>6.2f}  {r['pnl_pct']:>+6.2f}%  {r['days_held']:>5}  Rs {r['stop_loss']:>6.2f}  Rs {r['target_1']:>6.2f}")

# Waiting breakout
print()
print("=" * 80)
print("  WAITING BREAKOUT (not yet entered)")
print("=" * 80)
print(f"  {'Symbol':>16s}  {'Pattern':>20s}  {'Breakout':>8s}  {'Live':>8s}  {'Dist%':>7s}")
for _, r in waiting.sort_values('pnl_pct', ascending=False).iterrows():
    print(f"  {r['symbol']:>16s}  {r['pattern']:>20s}  Rs {r['breakout_level']:>6.2f}  Rs {r['live_price']:>6.2f}  {r['pnl_pct']:>+6.2f}%")

# Closed trades
closed = df[df['current_status'].isin(['WIN_T1', 'WIN_T2', 'LOSS', 'TIME_EXIT'])]
if len(closed) > 0:
    print()
    print("=" * 80)
    print("  CLOSED TRADES")
    print("=" * 80)
    for _, r in closed.iterrows():
        print(f"  {r['symbol']:>16s}  {r['current_status']:>10s}  P&L: {r['pnl_pct']:>+6.2f}%  exit: Rs {r.get('exit_price', 'N/A')}")

# Summary stats
print()
print("=" * 80)
print("  SUMMARY")
print("=" * 80)

# Open trades avg P&L
if len(open_trades) > 0:
    avg_open = open_trades['pnl_pct'].mean()
    best_open = open_trades['pnl_pct'].max()
    worst_open = open_trades['pnl_pct'].min()
    winners = len(open_trades[open_trades['pnl_pct'] > 0])
    print(f"  Open trades: {len(open_trades)}  Avg P&L: {avg_open:+.2f}%  Best: {best_open:+.2f}%  Worst: {worst_open:+.2f}%  In profit: {winners}/{len(open_trades)}")

if len(waiting) > 0:
    near_breakout = len(waiting[waiting['pnl_pct'] > -3])
    print(f"  Waiting breakout: {len(waiting)}  Near breakout (within 3%): {near_breakout}")

if len(closed) > 0:
    print(f"  Closed: {len(closed)}  Wins: {len(wins)}  Losses: {len(losses)}")

# Best performers
print()
print("  TOP 5 OPEN PERFORMERS:")
for _, r in open_trades.nlargest(5, 'pnl_pct').iterrows():
    print(f"    {r['symbol']:>16s}  {r['pnl_pct']:>+6.2f}%  ({r['pattern']})")

print()
print("  WORST 5 OPEN PERFORMERS:")
for _, r in open_trades.nsmallest(5, 'pnl_pct').iterrows():
    print(f"    {r['symbol']:>16s}  {r['pnl_pct']:>+6.2f}%  ({r['pattern']})")

# Send to Telegram
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>v3 Scanner — Paper Tracker Performance (Today)</b>")
    lines.append(f"<b>Date: {datetime.now().strftime('%Y-%m-%d')} | Picks from: Jul 30-31 scan</b>")
    lines.append("")
    lines.append(f"Total picks: {len(df)}")
    lines.append(f"  OPEN (active): {len(open_trades)}")
    lines.append(f"  WAITING_BREAKOUT: {len(waiting)}")
    lines.append(f"  Closed (W/L/Time): {len(closed)}")
    lines.append("")

    if len(open_trades) > 0:
        avg_open = open_trades['pnl_pct'].mean()
        winners = len(open_trades[open_trades['pnl_pct'] > 0])
        lines.append(f"<b>OPEN TRADES ({len(open_trades)} active)</b>")
        lines.append(f"  Avg P&L: {avg_open:+.2f}%  In profit: {winners}/{len(open_trades)}")
        lines.append("")
        lines.append(f"  {'Symbol':>16s}  {'Entry':>8s}  {'Live':>8s}  {'P&L%':>7s}  {'Days':>5s}")
        for _, r in open_trades.sort_values('pnl_pct', ascending=False).iterrows():
            emoji = "+" if r['pnl_pct'] > 0 else ""
            lines.append(f"  {r['symbol']:>16s}  Rs {r['entry_price']:>6.2f}  Rs {r['live_price']:>6.2f}  {r['pnl_pct']:>+6.2f}%  {r['days_held']:>3}d")

    if len(waiting) > 0:
        lines.append("")
        lines.append(f"<b>WAITING BREAKOUT ({len(waiting)} not yet entered)</b>")
        near = len(waiting[waiting['pnl_pct'] > -3])
        lines.append(f"  Near breakout (within 3%): {near}/{len(waiting)}")
        lines.append(f"  {'Symbol':>16s}  {'Breakout':>8s}  {'Live':>8s}  {'Dist%':>7s}")
        for _, r in waiting.sort_values('pnl_pct', ascending=False).head(10).iterrows():
            lines.append(f"  {r['symbol']:>16s}  Rs {r['breakout_level']:>6.2f}  Rs {r['live_price']:>6.2f}  {r['pnl_pct']:>+6.2f}%")

    if len(closed) > 0:
        lines.append("")
        lines.append(f"<b>CLOSED TRADES ({len(closed)})</b>")
        for _, r in closed.iterrows():
            lines.append(f"  {r['symbol']:>16s}  {r['current_status']:>10s}  P&L: {r['pnl_pct']:>+6.2f}%")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    if len(open_trades) > 0:
        best = open_trades.nlargest(1, 'pnl_pct').iloc[0]
        worst = open_trades.nsmallest(1, 'pnl_pct').iloc[0]
        lines.append(f"Best: {best['symbol']} {best['pnl_pct']:+.2f}%")
        lines.append(f"Worst: {worst['symbol']} {worst['pnl_pct']:+.2f}%")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("Paper tracker. Not financial advice.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print(f"\n  [Telegram] {'Sent successfully' if ok else 'Failed to send'}")
