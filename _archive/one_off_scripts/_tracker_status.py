"""Clean status summary of paper tracker and send to Telegram."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date
from telegram_notify import send_telegram, _get_credentials

tracker = pd.read_csv('results/paper_tracker.csv')

# Categorize
open_trades = tracker[tracker['current_status'] == 'OPEN'].copy()
waiting = tracker[tracker['current_status'] == 'WAITING_BREAKOUT'].copy()
wins_t1 = tracker[tracker['current_status'] == 'WIN_T1'].copy()
losses = tracker[tracker['current_status'] == 'LOSS'].copy()
re_entered = tracker[tracker['current_status'] == 'RE_ENTERED'].copy()

# Sort open by P&L
open_trades = open_trades.sort_values('current_pnl_pct', ascending=False)

# Tradeable filter
tradeable = tracker[~tracker['tradeable'].isin(['SKIP_TIGHT', 'SKIP_WIDE'])]

print("=" * 110)
print("  PAPER TRADE TRACKER — scanner-v3 (updated %s)" % date.today())
print("=" * 110)
print()
print("  SUMMARY")
print("  -------")
print(f"  Total picks:      {len(tracker)}")
print(f"  Open trades:      {len(open_trades)}")
print(f"  Waiting breakout: {len(waiting)}")
print(f"  Wins (T1 hit):    {len(wins_t1)}")
print(f"  Losses (SL hit):  {len(losses)}")
print(f"  Re-entered:       {len(re_entered)}")
print()

# Open trades table
print("  OPEN TRADES (sorted by P&L)")
print("  %-16s %-22s %8s %8s %8s %8s %7s %4s %-12s" % (
    "Symbol", "Pattern", "Entry", "SL", "T1", "Now", "P&L%", "Days", "Tradeable"))
print("  " + "-" * 105)
for _, r in open_trades.iterrows():
    print("  %-16s %-22s %8.2f %8.2f %8.2f %8.2f %+6.2f%% %4d %-12s" % (
        r['symbol'], r['pattern'][:22], r['entry_price'], r['stop_loss'],
        r['target_1'], r['current_price'], r['current_pnl_pct'],
        r['days_held'], r['tradeable']))

# Stats
if len(open_trades) > 0:
    pnls = open_trades['current_pnl_pct']
    n_profit = (pnls > 0).sum()
    n_loss = (pnls < 0).sum()
    avg_pnl = pnls.mean()
    total_pnl = pnls.sum()
    best = open_trades.iloc[0]
    worst = open_trades.iloc[-1]

    print()
    print("  OPEN TRADES STATS")
    print("  -------")
    print(f"  Profit/Loss:      {n_profit}/{len(open_trades)} in profit, {n_loss} in loss")
    print(f"  Avg P&L:          {avg_pnl:+.2f}%")
    print(f"  Total P&L:        {total_pnl:+.2f}% (sum of %)")
    print(f"  Best:             {best['symbol']} {best['current_pnl_pct']:+.2f}%")
    print(f"  Worst:            {worst['symbol']} {worst['current_pnl_pct']:+.2f}%")
    print(f"  Avg days held:    {open_trades['days_held'].mean():.1f}")

# Waiting for breakout
if len(waiting) > 0:
    print()
    print("  WAITING FOR BREAKOUT")
    print("  %-16s %-22s %8s %8s %7s" % ("Symbol", "Pattern", "Breakout", "Now", "Dist%"))
    print("  " + "-" * 65)
    for _, r in waiting.sort_values('current_pnl_pct', ascending=False).iterrows():
        dist = (r['current_price'] - r['breakout_level']) / r['breakout_level'] * 100
        print("  %-16s %-22s %8.2f %8.2f %+6.2f%%" % (
            r['symbol'], r['pattern'][:22], r['breakout_level'], r['current_price'], dist))

# Wins
if len(wins_t1) > 0:
    print()
    print("  WINS (T1 hit, still open for T2)")
    for _, r in wins_t1.iterrows():
        print(f"    {r['symbol']:16s}  entry {r['entry_price']:.2f}  T1 {r['target_1']:.2f}  T2 {r['target_2']:.2f}  now {r['current_price']:.2f}")

# Losses
if len(losses) > 0:
    print()
    print("  LOSSES (SL hit)")
    for _, r in losses.iterrows():
        print(f"    {r['symbol']:16s}  entry {r['entry_price']:.2f}  SL {r['stop_loss']:.2f}  P&L {r['current_pnl_pct']:+.2f}%")

# Re-entered
if len(re_entered) > 0:
    print()
    print("  RE-ENTERED (recovery after SL)")
    for _, r in re_entered.iterrows():
        print(f"    {r['symbol']:16s}  re-entry {r['entry_price']:.2f}  now {r['current_price']:.2f}  P&L {r['current_pnl_pct']:+.2f}%")

# Closed trade summary
closed = tracker[tracker['current_status'].isin(['LOSS', 'WIN_T2', 'TIME_EXIT'])]
if len(closed) > 0:
    print()
    print("  CLOSED TRADES SUMMARY")
    print(f"  Total closed: {len(closed)}")
    wins = closed[closed['current_status'].isin(['WIN_T2'])]
    real_losses = closed[closed['current_status'] == 'LOSS']
    print(f"  Wins: {len(wins)}  |  Losses: {len(real_losses)}")
    if len(closed) > 0:
        avg_pnl = closed['current_pnl_pct'].mean()
        print(f"  Avg P&L: {avg_pnl:+.2f}%")

# Send to Telegram
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>Paper Tracker Update — %s</b>" % date.today())
    lines.append("")
    lines.append("<b>SUMMARY</b>")
    lines.append(f"  Open: {len(open_trades)}  |  Waiting: {len(waiting)}  |  Wins: {len(wins_t1)}  |  Losses: {len(losses)}  |  Re-entered: {len(re_entered)}")
    lines.append("")

    if len(open_trades) > 0:
        pnls = open_trades['current_pnl_pct']
        lines.append(f"<b>OPEN TRADES ({len(open_trades)})</b>")
        lines.append(f"  {pnls[pnls > 0].count()}/{len(open_trades)} in profit  |  Avg: {pnls.mean():+.2f}%  |  Total: {pnls.sum():+.2f}%")
        lines.append("")
        lines.append("%-14s  %7s  %7s  %6s  %4s  %s" % ("Symbol", "Entry", "Now", "P&L%", "Days", "Pattern"))
        lines.append("-" * 60)
        for _, r in open_trades.iterrows():
            emoji = "+" if r['current_pnl_pct'] > 0 else " "
            lines.append("%-14s  %7.2f  %7.2f  %s%5.2f  %3d  %s" % (
                r['symbol'], r['entry_price'], r['current_price'],
                emoji, r['current_pnl_pct'], r['days_held'],
                r['pattern'][:20]))

    if len(waiting) > 0:
        lines.append("")
        lines.append(f"<b>WAITING BREAKOUT ({len(waiting)})</b>")
        for _, r in waiting.sort_values('current_pnl_pct', ascending=False).iterrows():
            dist = (r['current_price'] - r['breakout_level']) / r['breakout_level'] * 100
            lines.append(f"  {r['symbol']:14s}  now {r['current_price']:.2f}  vs BO {r['breakout_level']:.2f}  ({dist:+.1f}%)")

    if len(wins_t1) > 0:
        lines.append("")
        lines.append(f"<b>WINS — T1 HIT ({len(wins_t1)})</b>")
        for _, r in wins_t1.iterrows():
            lines.append(f"  {r['symbol']:14s}  entry {r['entry_price']:.2f}  T1 {r['target_1']:.2f}  now {r['current_price']:.2f}")

    if len(losses) > 0:
        lines.append("")
        lines.append(f"<b>LOSSES — SL HIT ({len(losses)})</b>")
        for _, r in losses.iterrows():
            lines.append(f"  {r['symbol']:14s}  entry {r['entry_price']:.2f}  SL {r['stop_loss']:.2f}  P&L {r['current_pnl_pct']:+.2f}%")

    if len(re_entered) > 0:
        lines.append("")
        lines.append(f"<b>RE-ENTERED ({len(re_entered)})</b>")
        for _, r in re_entered.iterrows():
            lines.append(f"  {r['symbol']:14s}  re-entry {r['entry_price']:.2f}  now {r['current_price']:.2f}  P&L {r['current_pnl_pct']:+.2f}%")

    # Best performers
    if len(open_trades) > 0:
        lines.append("")
        lines.append("<b>TOP PERFORMERS</b>")
        for _, r in open_trades.head(3).iterrows():
            lines.append(f"  {r['symbol']:14s}  {r['current_pnl_pct']:+.2f}%  ({r['pattern'][:20]})")

    lines.append("")
    lines.append("Not financial advice. For research only.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print(f"\n  [Telegram] {'Sent' if ok else 'Failed'}")
