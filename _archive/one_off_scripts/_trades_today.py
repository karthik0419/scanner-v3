"""Check what trades are actionable today — breakouts, T1 hits, stop alerts."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from data.loader import _fetch_nse
from utils.sector_rotation_v3 import get_stock_sector, get_hot_sectors
from telegram_notify import send_telegram, _get_credentials

tracker = pd.read_csv('results/paper_tracker.csv')

# ── Live prices ──
print("Fetching live prices...")
prices = {}
day_chg = {}
volumes = {}
for sym in tracker['symbol'].unique():
    try:
        df = _fetch_nse(sym.replace('.NS',''), days=5)
        if df is not None and not df.empty:
            prices[sym] = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2]) if len(df) > 1 else prices[sym]
            day_chg[sym] = (prices[sym] - prev) / prev * 100
            vol_today = float(df['Volume'].iloc[-1])
            vol_avg   = float(df['Volume'].tail(5).mean())
            volumes[sym] = vol_today / vol_avg if vol_avg > 0 else 1.0
    except:
        pass

# ── Hot sectors ──
hot_raw = get_hot_sectors(top_n=5)
hot_names = [h[0] for h in hot_raw] if hot_raw else []

# ── Nifty regime ──
nifty = yf.Ticker('^NSEI').history(period='1y')
if nifty.index.tz: nifty.index = nifty.index.tz_localize(None)
nifty_close = float(nifty['Close'].iloc[-1])
nifty_sma200 = float(nifty['Close'].rolling(200).mean().iloc[-1])
nifty_chg = (nifty_close / float(nifty['Close'].iloc[-2]) - 1) * 100
regime = 'BULL' if nifty_close > nifty_sma200 else 'BEAR'

print()
print("=" * 100)
print(f"  TRADES FOR TODAY — {date.today()}  |  Nifty {nifty_close:.0f} ({nifty_chg:+.2f}%)  |  Regime: {regime}")
print(f"  Hot sectors: {', '.join(hot_names[:5])}")
print("=" * 100)

waiting   = tracker[tracker['current_status'] == 'WAITING_BREAKOUT']
open_t    = tracker[tracker['current_status'] == 'OPEN']
win_t1    = tracker[tracker['current_status'] == 'WIN_T1']

buy_now   = []   # waiting that broke out today
near_bo   = []   # waiting within 1%
exits_t1  = []   # open that hit T1
exits_t2  = []   # open that hit T2
near_stop = []   # open within 2% of SL

# ── Check waiting list ──
print()
print("  WAITING LIST")
print("  %-16s  %-22s  %8s  %8s  %7s  %7s  %5s  %s" % (
    "Symbol", "Pattern", "BO", "Now", "Dist%", "Day%", "Vol", "Action"))
print("  " + "-" * 90)

for _, r in waiting.iterrows():
    sym  = r['symbol']
    cur  = prices.get(sym, 0)
    if cur == 0: continue
    bo   = float(r['breakout_level'])
    t1   = float(r['target_1'])
    t2   = float(r['target_2'])
    stop = float(r['stop_loss'])
    dist = (cur - bo) / bo * 100
    dc   = day_chg.get(sym, 0)
    vol  = volumes.get(sym, 1)
    sect = r['sector']
    is_hot = sect in hot_names

    if cur >= bo:
        action = ">>> BUY NOW"
        buy_now.append(r)
    elif dist > -1:
        action = "SET ALERT"
        near_bo.append(r)
    elif dist > -3:
        action = "watch"
    else:
        action = "too far"

    hot_flag = " *HOT*" if is_hot else ""
    print("  %-16s  %-22s  %8.2f  %8.2f  %+6.1f%%  %+6.1f%%  %4.1fx  %s%s" % (
        sym, r['pattern'][:22], bo, cur, dist, dc, vol, action, hot_flag))

# ── Check open trades ──
print()
print("  OPEN TRADES")
print("  %-16s  %-22s  %8s  %8s  %8s  %8s  %7s  %7s  %7s  %s" % (
    "Symbol", "Pattern", "Entry", "Now", "SL", "T1", "P&L%", "to_SL%", "to_T1%", "Alert"))
print("  " + "-" * 110)

for _, r in open_t.iterrows():
    sym   = r['symbol']
    cur   = prices.get(sym, 0)
    if cur == 0: continue
    entry = float(r['entry_price'])
    stop  = float(r['stop_loss'])
    t1    = float(r['target_1'])
    t2    = float(r['target_2'])
    pnl   = (cur - entry) / entry * 100
    to_sl = (cur - stop)  / cur   * 100
    to_t1 = (t1 - cur)    / cur   * 100
    to_t2 = (t2 - cur)    / cur   * 100
    dc    = day_chg.get(sym, 0)
    vol   = volumes.get(sym, 1)

    alert = ""
    if cur >= t2:
        alert = ">>> T2 HIT — EXIT ALL"
        exits_t2.append(r)
    elif cur >= t1:
        alert = ">>> T1 HIT — EXIT HALF"
        exits_t1.append(r)
    elif to_sl <= 2:
        alert = "!!! NEAR STOP LOSS"
        near_stop.append(r)
    elif to_sl <= 5:
        alert = "! watch stop"

    print("  %-16s  %-22s  %8.2f  %8.2f  %8.2f  %8.2f  %+6.1f%%  %+6.1f%%  %+6.1f%%  %s" % (
        sym, r['pattern'][:22], entry, cur, stop, t1, pnl, to_sl, to_t1, alert))

# ── T1 still open (WIN_T1) ──
if len(win_t1) > 0:
    print()
    print("  WIN T1 — STILL OPEN FOR T2")
    print("  %-16s  %8s  %8s  %8s  %8s  %s" % ("Symbol","Entry","T1","T2","Now","Status"))
    print("  " + "-" * 70)
    for _, r in win_t1.iterrows():
        sym = r['symbol']
        cur = prices.get(sym, 0)
        t2  = float(r['target_2'])
        to_t2 = (t2 - cur) / cur * 100 if cur > 0 else 0
        print("  %-16s  %8.2f  %8.2f  %8.2f  %8.2f  %+.1f%% to T2" % (
            sym, r['entry_price'], r['target_1'], t2, cur, to_t2))

# ── Summary ──
print()
print("=" * 100)
print("  ACTION SUMMARY")
print("=" * 100)

if buy_now:
    print()
    print("  BUY NOW (broke out today):")
    for r in buy_now:
        sym  = r['symbol']
        cur  = prices.get(sym, 0)
        stop = float(r['stop_loss'])
        t1   = float(r['target_1'])
        t2   = float(r['target_2'])
        rr   = float(r['rr'])
        risk = (cur - stop) / cur * 100 if cur > 0 else 0
        sect = r['sector']
        print(f"    {sym:16s}  Buy {cur:.2f}  SL {stop:.2f} ({risk:.1f}% risk)  T1 {t1:.2f}  T2 {t2:.2f}  R:R 1:{rr}  {sect}")

if near_bo:
    print()
    print("  SET ALERT (within 1% of breakout — may trigger today):")
    for r in near_bo:
        sym  = r['symbol']
        cur  = prices.get(sym, 0)
        bo   = float(r['breakout_level'])
        dist = (cur - bo) / bo * 100
        t1   = float(r['target_1'])
        t2   = float(r['target_2'])
        dc   = day_chg.get(sym, 0)
        vol  = volumes.get(sym, 1)
        print(f"    {sym:16s}  BO {bo:.2f}  Now {cur:.2f} ({dist:+.1f}%)  Day {dc:+.1f}%  Vol {vol:.1f}x  T1 {t1:.2f}  T2 {t2:.2f}")

if exits_t1:
    print()
    print("  EXIT HALF — T1 HIT:")
    for r in exits_t1:
        sym = r['symbol']
        cur = prices.get(sym, 0)
        t1  = float(r['target_1'])
        t2  = float(r['target_2'])
        print(f"    {sym:16s}  T1={t1:.2f}  Now={cur:.2f}  T2={t2:.2f}  -> Sell 50%, hold rest for T2, move SL to breakeven")

if exits_t2:
    print()
    print("  EXIT ALL — T2 HIT:")
    for r in exits_t2:
        sym = r['symbol']
        cur = prices.get(sym, 0)
        print(f"    {sym:16s}  T2={r['target_2']:.2f}  Now={cur:.2f}  -> Sell full position")

if near_stop:
    print()
    print("  WATCH STOPS (within 2%):")
    for r in near_stop:
        sym   = r['symbol']
        cur   = prices.get(sym, 0)
        stop  = float(r['stop_loss'])
        to_sl = (cur - stop) / cur * 100
        print(f"    {sym:16s}  SL={stop:.2f}  Now={cur:.2f}  ({to_sl:+.1f}% to stop)  -> Prepare to exit if hits SL")

if not buy_now and not near_bo and not exits_t1 and not exits_t2 and not near_stop:
    print()
    print("  No immediate action needed.")
    print("  All open trades healthy, no breakouts yet.")

print()
print(f"  Regime: {regime}  |  Hot sectors: {', '.join(hot_names[:3])}")
if regime == 'BEAR':
    print("  BEAR regime — consider smaller position sizes on new entries")

# ── Telegram ──
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append(f"<b>Trades for Today — {date.today()}</b>")
    lines.append(f"Nifty {nifty_close:.0f} ({nifty_chg:+.2f}%)  |  {regime}  |  Hot: {', '.join(hot_names[:3])}")
    lines.append("")

    if buy_now:
        lines.append("<b>BUY NOW (broke out)</b>")
        for r in buy_now:
            sym  = r['symbol']
            cur  = prices.get(sym, 0)
            stop = float(r['stop_loss'])
            t1   = float(r['target_1'])
            t2   = float(r['target_2'])
            risk = (cur - stop) / cur * 100 if cur > 0 else 0
            lines.append(f"  {sym:14s}  Buy {cur:.2f}  SL {stop:.2f} ({risk:.1f}%)  T1 {t1:.2f} -> T2 {t2:.2f}  R:R 1:{r['rr']}")
        lines.append("")

    if near_bo:
        lines.append("<b>SET ALERT (within 1% of BO)</b>")
        for r in near_bo:
            sym  = r['symbol']
            cur  = prices.get(sym, 0)
            bo   = float(r['breakout_level'])
            dist = (cur - bo) / bo * 100
            dc   = day_chg.get(sym, 0)
            vol  = volumes.get(sym, 1)
            lines.append(f"  {sym:14s}  BO {bo:.2f}  Now {cur:.2f} ({dist:+.1f}%)  Day {dc:+.1f}%  Vol {vol:.1f}x")
        lines.append("")

    if exits_t1:
        lines.append("<b>EXIT HALF — T1 HIT</b>")
        for r in exits_t1:
            sym = r['symbol']
            cur = prices.get(sym, 0)
            lines.append(f"  {sym:14s}  T1={r['target_1']:.2f}  Now={cur:.2f}  -> Sell 50%, trail to breakeven")
        lines.append("")

    if exits_t2:
        lines.append("<b>EXIT ALL — T2 HIT</b>")
        for r in exits_t2:
            sym = r['symbol']
            cur = prices.get(sym, 0)
            lines.append(f"  {sym:14s}  T2={r['target_2']:.2f}  Now={cur:.2f}  -> Sell full")
        lines.append("")

    if near_stop:
        lines.append("<b>WATCH STOP (within 2%)</b>")
        for r in near_stop:
            sym   = r['symbol']
            cur   = prices.get(sym, 0)
            stop  = float(r['stop_loss'])
            to_sl = (cur - stop) / cur * 100
            lines.append(f"  {sym:14s}  SL={stop:.2f}  Now={cur:.2f}  ({to_sl:+.1f}%)")
        lines.append("")

    if not buy_now and not near_bo and not exits_t1 and not exits_t2 and not near_stop:
        lines.append("No immediate action today.")
        lines.append("All trades healthy.")

    if regime == 'BEAR':
        lines.append("BEAR regime — smaller sizes on new entries")
    lines.append("")
    lines.append("Not financial advice.")

    ok = send_telegram(token, chat_id, "\n".join(lines))
    print(f"\n  [Telegram] {'Sent' if ok else 'Failed'}")
