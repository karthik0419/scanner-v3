"""Update TECHM and VEDL stops, then check all trades against correct stops."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from data.loader import _fetch_nse

tracker = pd.read_csv('results/paper_tracker.csv')

# Fix stops
for idx, row in tracker.iterrows():
    if row['symbol'] == 'TECHM.NS':
        tracker.at[idx, 'stop_loss'] = 1600.0
        print(f"TECHM stop updated: 1530 -> 1600")
    if row['symbol'] == 'VEDL.NS':
        tracker.at[idx, 'stop_loss'] = 250.0
        print(f"VEDL stop updated: 246.10 -> 250")

tracker.to_csv('results/paper_tracker.csv', index=False)
print("Tracker saved.")

# Now check all open trades with fresh prices
print()
print("=" * 100)
print("  TRADE CHECK — with corrected stops")
print("=" * 100)

open_t = tracker[tracker['current_status'] == 'OPEN']
prices = {}
for sym in open_t['symbol'].unique():
    try:
        df = _fetch_nse(sym.replace('.NS',''), days=5)
        if df is not None and not df.empty:
            prices[sym] = float(df['Close'].iloc[-1])
    except:
        pass

alerts = []
print()
print("  %-16s  %8s  %8s  %8s  %8s  %7s  %7s  %7s  %s" % (
    "Symbol", "Entry", "SL", "T1", "Now", "P&L%", "to_SL%", "to_T1%", "Alert"))
print("  " + "-" * 100)

for _, r in open_t.iterrows():
    sym   = r['symbol']
    cur   = prices.get(sym, float(r['current_price']))
    if cur == 0: continue
    entry = float(r['entry_price'])
    stop  = float(r['stop_loss'])
    t1    = float(r['target_1'])
    t2    = float(r['target_2'])
    pnl   = (cur - entry) / entry * 100
    to_sl = (cur - stop)  / cur   * 100
    to_t1 = (t1 - cur)    / cur   * 100

    alert = ""
    if cur <= stop:
        alert = ">>> STOP HIT — EXIT NOW"
        alerts.append((sym, "STOP HIT", cur, stop))
    elif cur >= t2:
        alert = ">>> T2 HIT — EXIT ALL"
        alerts.append((sym, "T2 HIT", cur, t2))
    elif cur >= t1:
        alert = ">>> T1 HIT — SELL HALF"
        alerts.append((sym, "T1 HIT", cur, t1))
    elif to_sl <= 2:
        alert = "!!! NEAR STOP"
        alerts.append((sym, "NEAR STOP", cur, stop))
    elif to_sl <= 5:
        alert = "! watch stop"
    elif to_t1 <= 3:
        alert = "near T1"

    print("  %-16s  %8.2f  %8.2f  %8.2f  %8.2f  %+6.1f%%  %+6.1f%%  %+6.1f%%  %s" % (
        sym, entry, stop, t1, cur, pnl, to_sl, to_t1, alert))

# Specifically check TECHM and VEDL
print()
print("=" * 100)
print("  TECHM & VEDL — DETAILED")
print("=" * 100)

for sym, entry, stop, t1, t2 in [
    ('TECHM.NS', 1589, 1600, 1687, 1750),
    ('VEDL.NS', 259.35, 250, 330.10, 411.83),
]:
    cur = prices.get(sym, 0)
    if cur == 0: continue
    pnl = (cur - entry) / entry * 100
    to_sl = (cur - stop) / cur * 100
    to_t1 = (t1 - cur) / cur * 100
    to_t2 = (t2 - cur) / cur * 100
    print()
    print(f"  {sym}")
    print(f"    Entry: {entry:.2f}  |  Now: {cur:.2f}  |  P&L: {pnl:+.2f}%")
    print(f"    SL: {stop:.2f}  ({to_sl:+.1f}% away)")
    print(f"    T1: {t1:.2f}  ({to_t1:+.1f}% away)")
    print(f"    T2: {t2:.2f}  ({to_t2:+.1f}% away)")
    if to_sl <= 3:
        print(f"    >>> WARNING: Only {to_sl:.1f}% above SL — tight!")
    if to_t1 <= 5:
        print(f"    >>> Near T1 — prepare to sell half")

# Summary
print()
print("=" * 100)
print("  ACTION NEEDED")
print("=" * 100)
if alerts:
    for sym, reason, cur, level in alerts:
        if reason == "STOP HIT":
            print(f"  EXIT NOW: {sym} at {cur:.2f} (SL {level:.2f})")
        elif reason == "T1 HIT":
            print(f"  SELL HALF: {sym} at {cur:.2f} (T1 {level:.2f})")
        elif reason == "T2 HIT":
            print(f"  EXIT ALL: {sym} at {cur:.2f} (T2 {level:.2f})")
        elif reason == "NEAR STOP":
            print(f"  WATCH: {sym} at {cur:.2f} (SL {level:.2f}, only {((cur-level)/cur*100):.1f}% away)")
else:
    print("  No alerts — all trades healthy")
