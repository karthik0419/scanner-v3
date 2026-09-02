"""
Enhanced v3.1 Daily Scan — with learnings from chart analysis (2026-08-05):

NEW vs standard daily_scan.py:
1. % of measured move done/left — shows how much upside remains
2. Upside remaining filter — skips picks with <10% move left
3. Targets formatted as "T1 to T2" range on one line
4. Historical resistance check — flags if prior high is near target
5. Double confirmation bonus — channel + S&R zone on same stock
6. Breakout sustained flag — held above BO for 10+ days
7. Nested cup detection — multiple cup lengths flagging same stock
"""
import sys, os, warnings
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from backtester.engine import _detect_signal, _score, _apply_atr_stop, _add_targets, _calc_atr, DETECTORS
from data.loader import _fetch_nse, _resample_weekly
from utils.sector_rotation_v3 import get_stock_sector, get_sector_bonus, get_hot_sectors
from telegram_notify import send_telegram, _get_credentials

# ─── Universe ───
def load_universe():
    stocks = set()
    for f in ['backbone50.txt', 'nifty200.txt']:
        if os.path.exists(f):
            with open(f) as fh:
                for line in fh:
                    s = line.strip()
                    if s and not s.startswith('#'):
                        stocks.add(s if s.endswith('.NS') else s + '.NS')
    return sorted(stocks)

UNIVERSE = load_universe()

# ─── Regime ───
print("Fetching Nifty regime...")
nifty = yf.Ticker('^NSEI').history(period='1y')
if nifty.index.tz: nifty.index = nifty.index.tz_localize(None)
nifty_close = float(nifty['Close'].iloc[-1])
nifty_sma50 = float(nifty['Close'].rolling(50).mean().iloc[-1])
nifty_sma200 = float(nifty['Close'].rolling(200).mean().iloc[-1])
nifty_chg = (nifty_close / float(nifty['Close'].iloc[-2]) - 1) * 100
regime = 'BULL' if nifty_close > nifty_sma50 and nifty_close > nifty_sma200 else 'BEAR'

# ─── Hot sectors ───
print("Getting hot sectors...")
hot_raw = get_hot_sectors(top_n=5)
hot_names = [h[0] for h in hot_raw] if hot_raw else []

print(f"Regime: {regime}  Nifty: {nifty_close:.0f} ({nifty_chg:+.2f}%)")
print(f"Hot sectors: {hot_names}")
print(f"Universe: {len(UNIVERSE)} stocks")
print()

# ─── Scan ───
picks = []

for i, sym in enumerate(UNIVERSE):
    if (i+1) % 50 == 0:
        print(f"  [{i+1}/{len(UNIVERSE)}] {len(picks)} picks...")
    try:
        df = _fetch_nse(sym.replace('.NS',''), days=400)
        if df is None or len(df) < 140:
            continue

        # Bad data check
        pct_chg = df['Close'].pct_change().abs()
        if (pct_chg > 0.40).any():
            continue

        df_weekly = _resample_weekly(df)

        # ── Run ALL detectors, collect all matches ──
        all_matches = []
        for name, detect, timeframe in DETECTORS:
            try:
                result = detect(df, df_weekly)
                if result:
                    result['timeframe'] = timeframe
                    result['detector'] = name
                    result = _add_targets(result)
                    result = _apply_atr_stop(result, df)
                    score, rr = _score(result)
                    result['score'] = score
                    result['rr'] = rr

                    cmp = result.get('cmp', 0)
                    stop = result.get('stop_loss', 0)
                    bo = result.get('breakout', 0)
                    risk = (cmp - stop) / cmp * 100 if cmp else 0
                    dist = abs(bo - cmp) / cmp * 100 if bo and cmp else 0
                    status = result.get('status', '')

                    if risk > 10: continue
                    if dist > 8 and status != 'BREAKOUT': continue
                    if score < 50 or rr <= 0: continue
                    if status not in ('BREAKOUT', 'NEAR'): continue

                    result['risk_pct'] = risk
                    result['dist_pct'] = (cmp - bo) / bo * 100 if bo else 0
                    all_matches.append(result)
            except:
                pass

        if not all_matches:
            continue

        # ── Learning #5: Nested cup detection ──
        cup_matches = [m for m in all_matches if 'Cup' in m.get('pattern','')]
        nested_bonus = 10 if len(cup_matches) >= 2 else 0
        if nested_bonus:
            for m in all_matches:
                m['nested_cup'] = True

        # ── Learning #3: Double confirmation bonus ──
        # Channel breakout + S&R zone within 2% of each other
        channel_matches = [m for m in all_matches if 'Channel' in m.get('pattern','') or 'Wedge' in m.get('pattern','')]
        sr_matches = [m for m in all_matches if 'S&R' in m.get('pattern','') or 'Breakout' in m.get('pattern','')]
        double_bonus = 0
        if channel_matches and sr_matches:
            for cm in channel_matches:
                for sm in sr_matches:
                    bo_diff = abs(cm.get('breakout',0) - sm.get('breakout',0)) / cm.get('breakout',1) * 100
                    if bo_diff < 2:
                        double_bonus = 15
                        break

        # Best match
        best = max(all_matches, key=lambda x: x['score'])
        score_adj = best['score'] + nested_bonus + double_bonus

        cmp = best.get('cmp', 0)
        bo = best.get('breakout', 0)
        t1 = best.get('target_1', 0)
        t2 = best.get('target_2', 0)
        stop = best.get('stop_loss', 0)

        # ── Learning #1: % of measured move done/left ──
        measured_move = t2 - bo if t2 > bo else 0
        if measured_move > 0 and bo > 0:
            pct_done = (cmp - bo) / measured_move * 100
            pct_left = 100 - pct_done
        else:
            pct_done = 0
            pct_left = 100

        # ── Learning #8: Skip if <10% upside remaining ──
        upside_from_cmp = (t2 - cmp) / cmp * 100 if cmp else 0
        if upside_from_cmp < 10:
            continue

        # ── Learning #2: Historical resistance near target ──
        hist_resist = None
        if len(df) >= 100:
            # Look for prior resistance in last 200 bars (before last 50)
            hist = df.iloc[-200:-50] if len(df) >= 200 else df.iloc[:-50]
            if len(hist) > 0:
                prior_high = float(hist['High'].max())
                # If prior high within 10% of T2, flag it
                if t2 > 0 and abs(prior_high - t2) / t2 < 0.10:
                    hist_resist = prior_high

        # ── Learning #4: Breakout sustained (held above BO 10+ days) ──
        sustained = False
        if bo > 0:
            recent_20 = df.tail(20)
            days_above_bo = (recent_20['Close'] >= bo).sum()
            if days_above_bo >= 10:
                sustained = True

        # ── Sector ──
        sector = get_stock_sector(sym)
        try:
            _, sector_signal, sector_bonus = get_sector_bonus(sym)
        except:
            sector_signal, sector_bonus = '', 0
        is_hot = sector in hot_names
        score_final = score_adj + (sector_bonus if sector_bonus else 0)

        # Volume
        vol_today = float(df['Volume'].iloc[-1])
        vol_avg20 = float(df['Volume'].tail(20).mean())
        vol_ratio = vol_today / vol_avg20 if vol_avg20 > 0 else 0

        # Day change
        day_chg = (float(df['Close'].iloc[-1]) / float(df['Close'].iloc[-2]) - 1) * 100

        picks.append({
            'symbol': sym,
            'pattern': best.get('pattern',''),
            'timeframe': best.get('timeframe',''),
            'status': best.get('status',''),
            'breakout': bo,
            'cmp': cmp,
            'stop': stop,
            't1': t1,
            't2': t2,
            'rr': best['rr'],
            'risk_pct': best.get('risk_pct', 0),
            'dist_pct': best.get('dist_pct', 0),
            'score': score_final,
            'score_base': best['score'],
            'nested_bonus': nested_bonus,
            'double_bonus': double_bonus,
            'sector': sector,
            'sector_signal': sector_signal,
            'is_hot': is_hot,
            'vol_ratio': vol_ratio,
            'day_chg': day_chg,
            'pct_done': pct_done,
            'pct_left': pct_left,
            'upside_from_cmp': upside_from_cmp,
            'hist_resist': hist_resist,
            'sustained': sustained,
            'n_patterns': len(all_matches),
        })

    except Exception as e:
        pass

# ─── Sort & display ───
picks.sort(key=lambda x: x['score'], reverse=True)
print(f"\nTotal picks: {len(picks)}")

print()
print("=" * 130)
print(f"  v3.1 ENHANCED SCAN — {date.today()}  |  Regime: {regime}  |  Nifty: {nifty_close:.0f} ({nifty_chg:+.2f}%)")
print(f"  Hot sectors: {', '.join(hot_names[:5])}")
print("=" * 130)
print()
print("  %-14s %-22s %-8s %-10s %8s %8s %16s %5s %5s %6s %5s %6s %5s %4s %4s %-14s" % (
    "Symbol", "Pattern", "TF", "Status", "CMP", "BO/SL", "Target (T1→T2)", "Risk%", "R:R",
    "Score", "Done%", "Left%", "Vol", "Day%", "Hot", "Sector"))
print("  " + "-" * 130)

for p in picks[:25]:
    hot_flag = "HOT" if p['is_hot'] else ""
    sustained_flag = " [S]" if p['sustained'] else ""
    nested_flag = " [N]" if p['nested_bonus'] else ""
    double_flag = " [D]" if p['double_bonus'] else ""
    flags = (sustained_flag + nested_flag + double_flag).strip()

    resist_note = f" ~R{p['hist_resist']:.0f}" if p['hist_resist'] else ""

    target_str = f"Rs {p['t1']:.0f}→{p['t2']:.0f}{resist_note}"

    print("  %-14s %-22s %-8s %-10s %8.2f %8.2f %-16s %4.1f%% %5.2f %6.1f %5.1f%% %5.1f%% %5.1fx %+4.1f%% %-4s %-14s %s" % (
        p['symbol'], p['pattern'][:22], p['timeframe'][:8], p['status'][:10],
        p['cmp'], p['stop'],
        target_str,
        p['risk_pct'], p['rr'],
        p['score'],
        p['pct_done'], p['pct_left'],
        p['vol_ratio'], p['day_chg'],
        hot_flag, p['sector'][:14],
        flags))

# ─── Special flags section ───
sustained_picks = [p for p in picks if p['sustained']]
nested_picks = [p for p in picks if p['nested_bonus']]
double_picks = [p for p in picks if p['double_bonus']]

if sustained_picks:
    print()
    print(f"  [S] BREAKOUT SUSTAINED (held >10 days above BO) — {len(sustained_picks)} stocks:")
    for p in sustained_picks[:5]:
        print(f"      {p['symbol']:14s}  {p['pattern']:22s}  BO {p['breakout']:.2f}  Now {p['cmp']:.2f}  {p['pct_done']:.0f}% done, {p['pct_left']:.0f}% left")

if nested_picks:
    print()
    print(f"  [N] NESTED CUP (multiple cup lengths detected) — {len(nested_picks)} stocks:")
    for p in nested_picks[:5]:
        print(f"      {p['symbol']:14s}  {p['n_patterns']} patterns  Score {p['score']:.0f}  {p['pct_left']:.0f}% left")

if double_picks:
    print()
    print(f"  [D] DOUBLE CONFIRMATION (channel + S&R) — {len(double_picks)} stocks:")
    for p in double_picks[:5]:
        print(f"      {p['symbol']:14s}  {p['pattern']:22s}  Score {p['score']:.0f}  {p['pct_left']:.0f}% left")

# ─── Top 5 summary ───
print()
print("=" * 130)
print("  TOP 5 ACTIONABLE PICKS")
print("=" * 130)
for i, p in enumerate(picks[:5]):
    flags = []
    if p['sustained']: flags.append('SUSTAINED')
    if p['nested_bonus']: flags.append('NESTED CUP')
    if p['double_bonus']: flags.append('DOUBLE CONFIRM')
    if p['is_hot']: flags.append('HOT SECTOR')
    if p['hist_resist']: flags.append(f'RESIST@{p["hist_resist"]:.0f}')
    flag_str = '  [' + ', '.join(flags) + ']' if flags else ''

    action = "BUY NOW" if p['status'] == 'BREAKOUT' else f"BUY above {p['breakout']:.2f}"
    print()
    print(f"  {i+1}. {p['symbol']} — {p['pattern']} [{p['timeframe']}]  Score: {p['score']:.0f}  {flag_str}")
    print(f"     {action}  |  SL: {p['stop']:.2f} ({p['risk_pct']:.1f}% risk)  |  Target: Rs {p['t1']:.0f} to {p['t2']:.0f}  |  R:R 1:{p['rr']:.2f}")
    print(f"     {p['pct_done']:.0f}% of move done, {p['pct_left']:.0f}% left ({p['upside_from_cmp']:.1f}% from CMP)  |  {p['sector']} ({p['sector_signal']})  |  Vol {p['vol_ratio']:.1f}x  |  Day {p['day_chg']:+.1f}%")

# ─── Telegram ───
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append(f"<b>v3.1 Enhanced Scan — {date.today()}</b>")
    lines.append(f"<b>Regime: {regime}  |  Nifty: {nifty_close:.0f} ({nifty_chg:+.2f}%)</b>")
    lines.append(f"Hot sectors: {', '.join(hot_names[:3])}")
    lines.append(f"Total picks: {len(picks)}  |  [S]={len(sustained_picks)} [N]={len(nested_picks)} [D]={len(double_picks)}")
    lines.append("")
    lines.append("<b>TOP 10 PICKS</b>")
    lines.append("%-14s  %-20s  %5s  %6s  %5s  %5s  %5s  %s" % (
        "Symbol", "Pattern", "Score", "CMP", "Risk%", "Done%", "Left%", "Action"))
    lines.append("-" * 75)

    for p in picks[:10]:
        flags = ""
        if p['sustained']: flags += "[S]"
        if p['nested_bonus']: flags += "[N]"
        if p['double_bonus']: flags += "[D]"
        if p['is_hot']: flags += "*"
        action = "BUY" if p['status'] == 'BREAKOUT' else f">{p['breakout']:.0f}"
        lines.append("%-14s  %-20s  %5.0f  %6.2f  %4.1f%%  %4.0f%%  %4.0f%%  %s %s" % (
            p['symbol'], p['pattern'][:20], p['score'], p['cmp'],
            p['risk_pct'], p['pct_done'], p['pct_left'], action, flags))

    lines.append("")
    lines.append("<b>TOP 5 DETAILS</b>")
    for i, p in enumerate(picks[:5]):
        flags = []
        if p['sustained']: flags.append('SUSTAINED')
        if p['nested_bonus']: flags.append('NESTED')
        if p['double_bonus']: flags.append('DOUBLE')
        if p['is_hot']: flags.append('HOT')
        lines.append(f"<b>{i+1}. {p['symbol']} — {p['pattern'][:20]} [{p['timeframe']}]</b>")
        lines.append(f"  Score {p['score']:.0f}  |  {', '.join(flags) if flags else 'standard'}")
        lines.append(f"  CMP {p['cmp']:.2f}  SL {p['stop']:.2f} ({p['risk_pct']:.1f}%)")
        lines.append(f"  Target: Rs {p['t1']:.0f} to {p['t2']:.0f}  R:R 1:{p['rr']:.2f}")
        lines.append(f"  {p['pct_done']:.0f}% done, {p['pct_left']:.0f}% left  Vol {p['vol_ratio']:.1f}x  {p['sector']}")
        lines.append("")

    lines.append("[S]=Sustained  [N]=Nested cup  [D]=Double confirm  *=Hot sector")
    lines.append("Not financial advice.")

    ok = send_telegram(token, chat_id, "\n".join(lines))
    print(f"\n  [Telegram] {'Sent' if ok else 'Failed'}")

print(f"\nDone. {len(picks)} picks found.")
