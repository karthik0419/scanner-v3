"""Add TECHM.NS to paper tracker with real buy price."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date

TRACKER_PATH = 'results/paper_tracker.csv'
tracker = pd.read_csv(TRACKER_PATH)

# Check if TECHM already in tracker
if 'TECHM.NS' in tracker['symbol'].values:
    print("TECHM.NS already in tracker — updating instead")
    idx = tracker[tracker['symbol'] == 'TECHM.NS'].index[0]
else:
    # Add new row
    # Entry: 1589 (actual buy price)
    # Stop: 1530 (below Jul 23 swing low of 1531 — 3.7% risk)
    # T1: 1687 (50-day high — +6.1% from entry)
    # T2: 1750 (extension target — +10.1% from entry)
    # Breakout: 1599 (Jul 26 breakout level)
    entry = 1589.0
    stop = 1530.0
    t1 = 1687.0
    t2 = 1750.0
    breakout = 1599.0
    current = 1650.0

    risk_pct = round((entry - stop) / entry * 100, 2)
    upside_pct = round((t1 - entry) / entry * 100, 2)
    rr = round((t1 - entry) / (entry - stop), 2)
    pnl_pct = round((current - entry) / entry * 100, 2)

    new_row = {
        'symbol': 'TECHM.NS',
        'pattern': 'Cup & Handle',
        'status_at_scan': 'BREAKOUT',
        'breakout_level': breakout,
        'entry_price': entry,
        'stop_loss': stop,
        'target_1': t1,
        'target_2': t2,
        'scan_date': '2026-07-22',
        'cmp_at_scan': 1555.80,
        'risk_pct': risk_pct,
        'upside_pct': upside_pct,
        'rr': rr,
        'score': 60.0,
        'sector': 'IT',
        'current_price': current,
        'current_status': 'OPEN',
        'current_pnl_pct': pnl_pct,
        'days_held': 14,
        'exit_price': '',
        'exit_date': '',
        'exit_reason': '',
        'tradeable': 'TRADE',
    }

    tracker = pd.concat([tracker, pd.DataFrame([new_row])], ignore_index=True)
    tracker.to_csv(TRACKER_PATH, index=False)

    print(f"Added TECHM.NS to tracker:")
    print(f"  Entry:  Rs {entry:.2f} (actual buy price)")
    print(f"  Stop:   Rs {stop:.2f}  (below Jul 23 swing low, {risk_pct}% risk)")
    print(f"  T1:     Rs {t1:.2f}  (50-day high, +{upside_pct}%)")
    print(f"  T2:     Rs {t2:.2f}  (extension, +{round((t2-entry)/entry*100, 1)}%)")
    print(f"  R:R:    1:{rr}")
    print(f"  Current: Rs {current:.2f}  ({pnl_pct:+.2f}%)")
    print(f"  Days held: 14")
    print(f"  Shares: 20 (Rs {entry*20:,.0f} invested)")
    print(f"  P&L:    Rs {pnl_pct/100*entry*20:+,.2f}")
    print(f"  Tracker saved: {TRACKER_PATH}")
