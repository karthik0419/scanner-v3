"""Check waiting list stocks with fresh prices, volume, and momentum.
Identify which are ready to enter NOW or tomorrow.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import date
from telegram_notify import send_telegram, _get_credentials
from data.loader import _fetch_nse
from utils.sector_rotation_v3 import get_stock_sector, get_sector_bonus, get_hot_sectors

tracker = pd.read_csv('results/paper_tracker.csv')
waiting = tracker[tracker['current_status'] == 'WAITING_BREAKOUT'].copy()

print("=" * 110)
print("  WAITING LIST ANALYSIS — Stocks ready to enter")
print("=" * 110)
print()

# Get hot sectors
hot = get_hot_sectors(top_n=5)
hot_names = [h[0] for h in hot] if hot else []
print(f"  Hot sectors: {hot_names}")
print()

results = []
for _, r in waiting.iterrows():
    sym = r['symbol']
    breakout = float(r['breakout_level'])
    entry = float(r['entry_price'])
    stop = float(r['stop_loss'])
    t1 = float(r['target_1'])
    t2 = float(r['target_2'])
    rr = float(r['rr'])
    score = float(r['score'])
    sector = r['sector']

    try:
        df = _fetch_nse(sym.replace('.NS', ''), days=60)
        if df is None or df.empty:
            continue

        cur = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2]) if len(df) > 1 else cur
        day_change = (cur - prev) / prev * 100

        dist_to_bo = (cur - breakout) / breakout * 100

        # Volume analysis
        vol_today = float(df['Volume'].iloc[-1])
        vol_avg_20 = float(df['Volume'].tail(20).mean())
        vol_ratio = vol_today / vol_avg_20 if vol_avg_20 > 0 else 0

        # Recent momentum (5-day)
        if len(df) >= 6:
            mom_5d = (cur / float(df['Close'].iloc[-6]) - 1) * 100
        else:
            mom_5d = 0

        # 20-day momentum
        if len(df) >= 21:
            mom_20d = (cur / float(df['Close'].iloc[-21]) - 1) * 100
        else:
            mom_20d = 0

        # Distance from stop
        dist_to_stop = (cur - stop) / cur * 100

        # Risk/reward from current price
        rr_from_cur = (t1 - cur) / (cur - stop) if (cur - stop) > 0 else 0

        # High/low of last 5 days
        high_5d = float(df['High'].tail(5).max())
        low_5d = float(df['Low'].tail(5).min())

        # Has it tested breakout recently?
        tested_breakout = high_5d >= breakout * 0.98

        # Sector heat
        try:
            _, sector_signal, sector_bonus = get_sector_bonus(sym)
        except:
            sector_signal, sector_bonus = 'Unknown', 0

        is_hot = sector in hot_names

        # Rating
        if dist_to_bo >= 0:
            rating = "BUY NOW"
            rating_color = "++"
        elif dist_to_bo > -1:
            rating = "WATCH CLOSE"
            rating_color = "++"
        elif dist_to_bo > -3:
            rating = "NEAR"
            rating_color = "+"
        elif dist_to_bo > -5:
            rating = "WAIT"
            rating_color = "-"
        else:
            rating = "FAR"
            rating_color = "--"

        results.append({
            'symbol': sym,
            'pattern': r['pattern'],
            'breakout': breakout,
            'current': cur,
            'dist_to_bo': dist_to_bo,
            'stop': stop,
            't1': t1,
            't2': t2,
            'rr': rr,
            'rr_from_cur': rr_from_cur,
            'score': score,
            'sector': sector,
            'sector_signal': sector_signal,
            'sector_bonus': sector_bonus,
            'is_hot': is_hot,
            'day_change': day_change,
            'vol_ratio': vol_ratio,
            'mom_5d': mom_5d,
            'mom_20d': mom_20d,
            'dist_to_stop': dist_to_stop,
            'high_5d': high_5d,
            'low_5d': low_5d,
            'tested_breakout': tested_breakout,
            'rating': rating,
        })
    except Exception as e:
        print(f"  Error fetching {sym}: {e}")

# Sort by distance to breakout (closest first)
results.sort(key=lambda x: x['dist_to_bo'], reverse=True)

print("  %-16s %-22s %8s %8s %7s %6s %7s %5s %5s %5s %-10s %-6s %-12s" % (
    "Symbol", "Pattern", "Breakout", "Now", "Dist%", "Day%", "Vol(x)", "R:R", "Score", "5d%", "Sector", "Hot?", "Rating"))
print("  " + "-" * 120)

for r in results:
    hot = "HOT" if r['is_hot'] else ""
    print("  %-16s %-22s %8.2f %8.2f %+6.2f%% %+5.2f%% %6.1fx %5.2f %5.1f %+5.1f%% %-10s %-6s %-12s" % (
        r['symbol'], r['pattern'][:22], r['breakout'], r['current'],
        r['dist_to_bo'], r['day_change'], r['vol_ratio'],
        r['rr'], r['score'], r['mom_5d'],
        r['sector'][:10], hot, r['rating']))

# Detailed analysis of top candidates
print()
print("=" * 110)
print("  DETAILED ANALYSIS — Top candidates to enter")
print("=" * 110)

buy_now = [r for r in results if r['dist_to_bo'] >= 0]
watch_close = [r for r in results if -1 <= r['dist_to_bo'] < 0]
near = [r for r in results if -3 <= r['dist_to_bo'] < -1]

for label, group in [("BUY NOW (broke out)", buy_now),
                      ("WATCH CLOSE (within 1%)", watch_close),
                      ("NEAR (within 3%)", near)]:
    if not group:
        continue
    print()
    print(f"  {label}:")
    print()
    for r in group:
        print(f"  {r['symbol']} ({r['pattern']})")
        print(f"    Breakout: Rs {r['breakout']:.2f}  |  Current: Rs {r['current']:.2f}  |  Distance: {r['dist_to_bo']:+.2f}%")
        print(f"    Stop: Rs {r['stop']:.2f}  |  T1: Rs {r['t1']:.2f}  |  T2: Rs {r['t2']:.2f}")
        print(f"    R:R: 1:{r['rr']}  |  Score: {r['score']}  |  Risk: {r['dist_to_stop']:.1f}%")
        print(f"    Sector: {r['sector']} ({r['sector_signal']}, {'HOT' if r['is_hot'] else 'not hot'})")
        print(f"    Today: {r['day_change']:+.2f}%  |  Vol: {r['vol_ratio']:.1f}x avg  |  5d: {r['mom_5d']:+.1f}%  |  20d: {r['mom_20d']:+.1f}%")
        print(f"    5d range: {r['low_5d']:.2f} - {r['high_5d']:.2f}  |  Tested BO: {'Yes' if r['tested_breakout'] else 'No'}")
        print()

# Summary recommendation
print("=" * 110)
print("  RECOMMENDATION")
print("=" * 110)
print()

if buy_now:
    print("  ENTER NOW (price above breakout):")
    for r in buy_now:
        print(f"    {r['symbol']:16s}  Buy at {r['current']:.2f}  SL {r['stop']:.2f}  T1 {r['t1']:.2f}  T2 {r['t2']:.2f}  R:R 1:{r['rr']}  {'[HOT]' if r['is_hot'] else ''}")
    print()

if watch_close:
    print("  SET ALERT (within 1% of breakout — may trigger tomorrow):")
    for r in watch_close:
        print(f"    {r['symbol']:16s}  BO {r['breakout']:.2f}  Now {r['current']:.2f}  ({r['dist_to_bo']:+.2f}%)  Buy above {r['breakout']:.2f}")
    print()

if near:
    print("  WATCH (within 3% — may trigger this week):")
    for r in near:
        print(f"    {r['symbol']:16s}  BO {r['breakout']:.2f}  Now {r['current']:.2f}  ({r['dist_to_bo']:+.2f}%)")
    print()

far = [r for r in results if r['dist_to_bo'] < -5]
if far:
    print("  SKIP (too far from breakout):")
    for r in far:
        print(f"    {r['symbol']:16s}  BO {r['breakout']:.2f}  Now {r['current']:.2f}  ({r['dist_to_bo']:+.2f}%)")
    print()

# Send to Telegram
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>Waiting List — Ready to Enter</b>")
    lines.append(f"<b>Date: {date.today()}</b>")
    lines.append("")

    if buy_now:
        lines.append("<b>ENTER NOW (above breakout)</b>")
        for r in buy_now:
            lines.append(f"  {r['symbol']:14s}  Buy {r['current']:.2f}  SL {r['stop']:.2f}  T1 {r['t1']:.2f}  R:R 1:{r['rr']}  {r['sector']} {'[HOT]' if r['is_hot'] else ''}")
        lines.append("")

    if watch_close:
        lines.append("<b>SET ALERT (within 1% of BO)</b>")
        for r in watch_close:
            lines.append(f"  {r['symbol']:14s}  BO {r['breakout']:.2f}  Now {r['current']:.2f}  ({r['dist_to_bo']:+.1f}%)  Vol {r['vol_ratio']:.1f}x  5d {r['mom_5d']:+.1f}%")
        lines.append("")

    if near:
        lines.append("<b>WATCH (within 3% of BO)</b>")
        for r in near:
            lines.append(f"  {r['symbol']:14s}  BO {r['breakout']:.2f}  Now {r['current']:.2f}  ({r['dist_to_bo']:+.1f}%)")
        lines.append("")

    lines.append(f"Hot sectors: {', '.join(hot_names[:3]) if hot_names else 'None'}")
    lines.append("")
    lines.append("Not financial advice.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print(f"  [Telegram] {'Sent' if ok else 'Failed'}")
