"""Find stocks that have broken out TODAY or recently — buyable now.
Also check the waiting list for breakouts.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date, timedelta
from telegram_notify import send_telegram, _get_credentials
from utils.sector_rotation_v3 import get_stock_sector, get_sector_bonus, get_hot_sectors

# ─── 1. Check waiting list for breakouts ───
print("=" * 100)
print("  1. WAITING LIST — Check if any broke out today")
print("=" * 100)

tracker = pd.read_csv('results/paper_tracker.csv')
waiting = tracker[tracker['current_status'] == 'WAITING_BREAKOUT'].copy()

from data.loader import _fetch_nse

broke_out = []
still_waiting = []
for _, r in waiting.iterrows():
    sym = r['symbol']
    breakout = float(r['breakout_level'])
    try:
        df = _fetch_nse(sym.replace('.NS', ''), days=5)
        if df is not None and not df.empty:
            cur = float(df['Close'].iloc[-1])
            dist = (cur - breakout) / breakout * 100
            if cur >= breakout:
                broke_out.append({
                    'symbol': sym,
                    'pattern': r['pattern'],
                    'breakout': breakout,
                    'current': cur,
                    'dist_pct': dist,
                    'entry': r['entry_price'],
                    'stop': r['stop_loss'],
                    't1': r['target_1'],
                    't2': r['target_2'],
                    'rr': r['rr'],
                    'score': r['score'],
                    'sector': r['sector'],
                })
                print(f"  [BROKE OUT] {sym:16s}  BO={breakout:.2f}  Now={cur:.2f}  ({dist:+.2f}%)  -> BUY")
            else:
                still_waiting.append({
                    'symbol': sym,
                    'breakout': breakout,
                    'current': cur,
                    'dist_pct': dist,
                })
                print(f"  [Waiting]   {sym:16s}  BO={breakout:.2f}  Now={cur:.2f}  ({dist:+.2f}%)")
    except Exception as e:
        print(f"  [Error]     {sym:16s}  {e}")

print(f"\n  Broke out: {len(broke_out)}  |  Still waiting: {len(still_waiting)}")

# ─── 2. Run fresh scan for new breakouts ───
print()
print("=" * 100)
print("  2. FRESH SCAN — New breakout picks (backbone50 + nifty200)")
print("=" * 100)

import warnings
warnings.filterwarnings('ignore')

from backtester.engine import _detect_signal, _score, _apply_atr_stop, _add_targets, _calc_atr
from data.loader import _resample_weekly

def load_universe():
    stocks = set()
    for f in ['backbone50.txt', 'nifty200.txt']:
        if os.path.exists(f):
            with open(f) as fh:
                for line in fh:
                    s = line.strip()
                    if s and not s.startswith('#'):
                        if not s.endswith('.NS'):
                            s = s + '.NS'
                        stocks.add(s)
    return sorted(stocks)

# Stocks already in tracker
in_tracker = set(tracker['symbol'].values)

UNIVERSE = load_universe()
print(f"  Universe: {len(UNIVERSE)} stocks (excluding {len(in_tracker)} already in tracker)")

# Get hot sectors
print("  Getting hot sectors...")
hot = get_hot_sectors(top_n=5)
print(f"  Hot sectors: {hot}")

# Get regime
nifty = yf.Ticker('^NSEI').history(period='1y')
if nifty.index.tz is not None:
    nifty.index = nifty.index.tz_localize(None)
nifty_close = float(nifty['Close'].iloc[-1])
nifty_sma50 = float(nifty['Close'].rolling(50).mean().iloc[-1])
nifty_sma200 = float(nifty['Close'].rolling(200).mean().iloc[-1])
regime = 'BULL' if nifty_close > nifty_sma50 and nifty_close > nifty_sma200 else 'BEAR'
print(f"  Regime: {regime}  (Nifty {nifty_close:.0f} vs SMA50 {nifty_sma50:.0f}, SMA200 {nifty_sma200:.0f})")

new_picks = []
for i, sym in enumerate(UNIVERSE):
    if sym in in_tracker:
        continue
    try:
        df = _fetch_nse(sym.replace('.NS', ''), days=365)
        if df is None or len(df) < 140:
            continue

        df_weekly = _resample_weekly(df)
        result = _detect_signal(df, df_weekly)
        if result is None:
            continue

        result = _add_targets(result)
        result = _apply_atr_stop(result, df)
        score, rr = _score(result)
        result['score'] = score
        result['rr'] = rr

        # Filters
        cmp_val = result.get('cmp', 0)
        stop_val = result.get('stop_loss', 0)
        bo_val = result.get('breakout', 0)
        risk_pct = (cmp_val - stop_val) / cmp_val * 100 if cmp_val else 0
        if risk_pct > 10:
            continue
        dist_pct = abs(bo_val - cmp_val) / cmp_val * 100 if bo_val and cmp_val else 0
        if bo_val > 0 and dist_pct > 8 and result.get('status') != 'BREAKOUT':
            continue

        if score < 50 or rr <= 0:
            continue

        # Only BREAKOUT or NEAR (within 3%)
        status = result.get('status', '')
        if status not in ('BREAKOUT', 'NEAR'):
            continue

        # Sector
        sector = get_stock_sector(sym)
        sector_signal, sector_bonus = '', 0
        try:
            _, sector_signal, sector_bonus = get_sector_bonus(sym)
        except:
            pass

        # Apply sector bonus to score
        score_adj = score + sector_bonus

        new_picks.append({
            'symbol': sym,
            'pattern': result.get('pattern', ''),
            'breakout': bo_val,
            'cmp': cmp_val,
            'entry': bo_val if status == 'NEAR' else cmp_val,
            'stop': stop_val,
            't1': result.get('target_1', 0),
            't2': result.get('target_2', 0),
            'rr': rr,
            'score': score,
            'score_adj': score_adj,
            'status': status,
            'risk_pct': risk_pct,
            'dist_pct': (cmp_val - bo_val) / bo_val * 100 if bo_val else 0,
            'sector': sector,
            'sector_signal': sector_signal,
            'sector_bonus': sector_bonus,
            'hot_sector': sector in hot if hot else False,
        })
    except:
        pass

print(f"  Found {len(new_picks)} picks")

# Sort by score
new_picks.sort(key=lambda x: x['score_adj'], reverse=True)

# ─── 3. Display results ───
print()
print("=" * 100)
print("  BUYABLE NOW — Already broke out (BREAKOUT status)")
print("=" * 100)
print()
print("  %-16s %-22s %8s %8s %8s %8s %6s %5s %5s %-12s %-10s" % (
    "Symbol", "Pattern", "Breakout", "CMP", "SL", "T1", "Risk%", "R:R", "Score", "Sector", "Hot?"))
print("  " + "-" * 115)

breakout_picks = [p for p in new_picks if p['status'] == 'BREAKOUT']
for p in breakout_picks[:20]:
    hot = "HOT" if p['hot_sector'] else ""
    print("  %-16s %-22s %8.2f %8.2f %8.2f %8.2f %5.1f%% %5.2f %5.1f %-12s %-10s" % (
        p['symbol'], p['pattern'][:22], p['breakout'], p['cmp'], p['stop'],
        p['t1'], p['risk_pct'], p['rr'], p['score_adj'], p['sector'][:12], hot))

print()
print("=" * 100)
print("  WATCHLIST — Near breakout (within 3%, buy on breakout)")
print("=" * 100)
print()
print("  %-16s %-22s %8s %8s %6s %5s %5s %-12s %-10s" % (
    "Symbol", "Pattern", "Breakout", "CMP", "Dist%", "R:R", "Score", "Sector", "Hot?"))
print("  " + "-" * 100)

near_picks = [p for p in new_picks if p['status'] == 'NEAR']
near_picks.sort(key=lambda x: abs(x['dist_pct']))
for p in near_picks[:15]:
    hot = "HOT" if p['hot_sector'] else ""
    print("  %-16s %-22s %8.2f %8.2f %+5.1f%% %5.2f %5.1f %-12s %-10s" % (
        p['symbol'], p['pattern'][:22], p['breakout'], p['cmp'],
        p['dist_pct'], p['rr'], p['score_adj'], p['sector'][:12], hot))

# ─── 4. Combined recommendation ───
all_buyable = broke_out + [
    p for p in breakout_picks if p['hot_sector'] or p['score_adj'] >= 60
]

print()
print("=" * 100)
print("  TOP RECOMMENDATIONS — Buy now")
print("=" * 100)
print()

# From waiting list that broke out
if broke_out:
    print("  FROM WAITING LIST (just broke out):")
    for p in broke_out:
        print(f"    {p['symbol']:16s}  BO={p['breakout']:.2f}  Now={p['current']:.2f}  "
              f"SL={p['stop']:.2f}  T1={p['t1']:.2f}  T2={p['t2']:.2f}  R:R=1:{p['rr']}  "
              f"Score={p['score']}  Sector={p['sector']}")
    print()

# New breakouts
if breakout_picks:
    print("  NEW BREAKOUTS (broke out today, buy at CMP):")
    top_new = [p for p in breakout_picks if p['score_adj'] >= 55][:8]
    for p in top_new:
        print(f"    {p['symbol']:16s}  CMP={p['cmp']:.2f}  SL={p['stop']:.2f}  "
              f"T1={p['t1']:.2f}  T2={p['t2']:.2f}  Risk={p['risk_pct']:.1f}%  "
              f"R:R=1:{p['rr']}  Score={p['score_adj']:.0f}  {p['sector']} {'[HOT]' if p['hot_sector'] else ''}")
    print()

# Near breakout
if near_picks:
    print("  NEAR BREAKOUT (buy when price crosses breakout level):")
    top_near = [p for p in near_picks if abs(p['dist_pct']) < 3][:5]
    for p in top_near:
        print(f"    {p['symbol']:16s}  BO={p['breakout']:.2f}  Now={p['cmp']:.2f}  "
              f"({p['dist_pct']:+.1f}%)  SL={p['stop']:.2f}  T1={p['t1']:.2f}  "
              f"R:R=1:{p['rr']}  Score={p['score_adj']:.0f}  {p['sector']}")
    print()

# ─── 5. Send to Telegram ───
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>Buyable Stocks — %s</b>" % date.today())
    lines.append(f"<b>Regime: {regime} | Hot: {', '.join(hot[:3]) if hot else 'None'}</b>")
    lines.append("")

    if broke_out:
        lines.append("<b>FROM WAITING LIST (broke out today)</b>")
        for p in broke_out:
            lines.append(f"  {p['symbol']:14s}  BO {p['breakout']:.2f}  Now {p['current']:.2f}  "
                        f"SL {p['stop']:.2f}  T1 {p['t1']:.2f}  R:R 1:{p['rr']}  {p['sector']}")
        lines.append("")

    if breakout_picks:
        top_new = [p for p in breakout_picks if p['score_adj'] >= 55][:8]
        if top_new:
            lines.append("<b>NEW BREAKOUTS (buy at CMP)</b>")
            lines.append("%-14s  %7s  %7s  %7s  %5s  %5s  %5s  %s" % (
                "Symbol", "CMP", "SL", "T1", "Risk%", "R:R", "Score", "Sector"))
            lines.append("-" * 70)
            for p in top_new:
                hot = " *" if p['hot_sector'] else ""
                lines.append("%-14s  %7.2f  %7.2f  %7.2f  %4.1f%%  1:%4.2f  %5.0f  %s%s" % (
                    p['symbol'], p['cmp'], p['stop'], p['t1'],
                    p['risk_pct'], p['rr'], p['score_adj'], p['sector'][:10], hot))
            lines.append("")

    if near_picks:
        top_near = [p for p in near_picks if abs(p['dist_pct']) < 3][:5]
        if top_near:
            lines.append("<b>NEAR BREAKOUT (buy on breakout)</b>")
            for p in top_near:
                lines.append(f"  {p['symbol']:14s}  BO {p['breakout']:.2f}  Now {p['cmp']:.2f}  "
                            f"({p['dist_pct']:+.1f}%)  T1 {p['t1']:.2f}  R:R 1:{p['rr']}  {p['sector']}")
            lines.append("")

    lines.append("* = hot sector  |  Not financial advice")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print(f"  [Telegram] {'Sent' if ok else 'Failed'}")
