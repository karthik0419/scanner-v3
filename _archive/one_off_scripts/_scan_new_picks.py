"""Run full v3.1 scan on THYROCARE and TILAKNAGAR, generate entry details."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from backtester.engine import _detect_signal, _score, _apply_atr_stop, _add_targets, _calc_atr
from data.loader import _fetch_nse, _resample_weekly
from utils.sector_rotation_v3 import get_stock_sector, get_sector_bonus
from telegram_notify import send_telegram, _get_credentials
import warnings
warnings.filterwarnings('ignore')

STOCKS = ['TI', 'THYROCARE']  # TI = Tilaknagar Industries

print("=" * 90)
print("  v3.1 FULL SCAN — TILAKNAGAR + THYROCARE")
print("=" * 90)

results = []

for sym in STOCKS:
    print(f"\n{'='*60}")
    print(f"  {sym}.NS")
    print(f"{'='*60}")

    df = _fetch_nse(sym, days=500)
    if df is None or len(df) < 140:
        # fallback to yfinance
        try:
            h = yf.Ticker(sym + '.NS').history(period='2y')
            if h.index.tz:
                h.index = h.index.tz_localize(None)
            df = h
        except:
            print(f"  No data for {sym}")
            continue

    if df is None or len(df) < 140:
        print(f"  Insufficient data ({len(df) if df is not None else 0} bars)")
        continue

    print(f"  Data: {len(df)} bars, {df.index[0].date()} to {df.index[-1].date()}")

    # Current price info
    cur = float(df['Close'].iloc[-1])
    prev = float(df['Close'].iloc[-2])
    day_chg = (cur - prev) / prev * 100
    vol_today = float(df['Volume'].iloc[-1])
    vol_avg20 = float(df['Volume'].tail(20).mean())
    vol_ratio = vol_today / vol_avg20 if vol_avg20 > 0 else 0
    atr = _calc_atr(df)

    print(f"  CMP: Rs {cur:.2f}  ({day_chg:+.2f}% today)")
    print(f"  Volume: {vol_ratio:.1f}x avg")
    print(f"  ATR(14): {atr:.2f}")

    # Check for bad data (>40% daily jump)
    pct = df['Close'].pct_change().abs()
    bad = pct[pct > 0.40]
    if len(bad) > 0:
        print(f"  WARNING: {len(bad)} day(s) with >40% jump — possible corporate action")
        print(f"  Dates: {list(bad.index[:3])}")
        # Remove bad bars and continue
        df = df[pct <= 0.40].copy()
        print(f"  Cleaned: {len(df)} bars remaining")

    if len(df) < 140:
        print(f"  Too few bars after cleaning")
        continue

    # Weekly resample
    df_weekly = _resample_weekly(df)
    print(f"  Weekly bars: {len(df_weekly)}")

    # Run all 15 detectors
    print()
    print("  Running v3.1 pattern detectors...")

    from backtester.engine import DETECTORS
    found = []
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

                cmp_val = result.get('cmp', 0)
                stop_val = result.get('stop_loss', 0)
                bo_val = result.get('breakout', 0)
                risk_pct = (cmp_val - stop_val) / cmp_val * 100 if cmp_val else 0
                dist_pct = abs(bo_val - cmp_val) / cmp_val * 100 if bo_val and cmp_val else 0

                print(f"  [{name:15s}] {result['pattern']:30s} [{timeframe:7s}]  "
                      f"BO={bo_val:.2f}  SL={stop_val:.2f}  T1={result.get('target_1',0):.2f}  "
                      f"T2={result.get('target_2',0):.2f}  Risk={risk_pct:.1f}%  R:R={rr:.2f}  Score={score:.0f}  "
                      f"Status={result.get('status','')}  Dist={dist_pct:.1f}%")
                found.append(result)
        except Exception as e:
            pass

    if not found:
        print("  No patterns detected.")
        continue

    # Best pattern
    best = max(found, key=lambda x: x['score'])
    print()
    print(f"  BEST PATTERN: {best['pattern']} [{best['timeframe']}]")
    print(f"  Status:    {best.get('status','')}")
    print(f"  Breakout:  Rs {best.get('breakout',0):.2f}")
    print(f"  Entry:     Rs {best.get('cmp',0):.2f}")
    print(f"  Stop Loss: Rs {best.get('stop_loss',0):.2f}  ({(best.get('cmp',0)-best.get('stop_loss',0))/best.get('cmp',1)*100:.1f}% risk)")
    print(f"  Target 1:  Rs {best.get('target_1',0):.2f}  ({(best.get('target_1',0)-best.get('cmp',0))/best.get('cmp',1)*100:+.1f}%)")
    print(f"  Target 2:  Rs {best.get('target_2',0):.2f}  ({(best.get('target_2',0)-best.get('cmp',0))/best.get('cmp',1)*100:+.1f}%)")
    print(f"  R:R:       1:{best['rr']:.2f}")
    print(f"  Score:     {best['score']:.1f}/100")
    print(f"  Volume:    {best.get('volume',False)}")
    print(f"  ATR:       {atr:.2f}")

    # Sector
    sector = get_stock_sector(sym + '.NS')
    try:
        _, sector_signal, sector_bonus = get_sector_bonus(sym + '.NS')
    except:
        sector_signal, sector_bonus = 'Unknown', 0
    print(f"  Sector:    {sector} ({sector_signal}, bonus {sector_bonus:+d})")

    # Tradeable assessment
    risk_pct = (best.get('cmp',0) - best.get('stop_loss',0)) / best.get('cmp',1) * 100
    dist_pct = abs(best.get('breakout',0) - best.get('cmp',0)) / best.get('cmp',1) * 100
    status = best.get('status','')

    print()
    if risk_pct > 10:
        verdict = "SKIP — risk too wide (>10%)"
    elif dist_pct > 8 and status != 'BREAKOUT':
        verdict = "SKIP — too far from breakout (>8%)"
    elif best['score'] < 50:
        verdict = "SKIP — score too low (<50)"
    elif status == 'BREAKOUT':
        verdict = "BUY NOW — already broke out"
    elif dist_pct < 3:
        verdict = "NEAR BREAKOUT — set alert, buy on BO"
    elif dist_pct < 8:
        verdict = "WATCH — within 8%, wait for breakout"
    else:
        verdict = "SKIP — too far"
    print(f"  VERDICT:   {verdict}")

    results.append({
        'symbol': sym + '.NS',
        'pattern': best['pattern'],
        'timeframe': best['timeframe'],
        'status': status,
        'breakout': best.get('breakout', 0),
        'cmp': best.get('cmp', 0),
        'stop': best.get('stop_loss', 0),
        't1': best.get('target_1', 0),
        't2': best.get('target_2', 0),
        'rr': best['rr'],
        'score': best['score'],
        'risk_pct': risk_pct,
        'dist_pct': dist_pct,
        'sector': sector,
        'sector_signal': sector_signal,
        'sector_bonus': sector_bonus,
        'vol_ratio': vol_ratio,
        'day_chg': day_chg,
        'verdict': verdict,
    })

# Final summary
print()
print("=" * 90)
print("  FINAL SUMMARY")
print("=" * 90)
print()
print("  %-16s %-25s %-8s %8s %8s %8s %8s %6s %5s %5s %-30s" % (
    "Symbol", "Pattern", "TF", "BO", "CMP", "SL", "T1", "Risk%", "R:R", "Score", "Verdict"))
print("  " + "-" * 115)
for r in results:
    print("  %-16s %-25s %-8s %8.2f %8.2f %8.2f %8.2f %5.1f%% %5.2f %5.1f %-30s" % (
        r['symbol'], r['pattern'][:25], r['timeframe'],
        r['breakout'], r['cmp'], r['stop'], r['t1'],
        r['risk_pct'], r['rr'], r['score'], r['verdict']))

# Send to Telegram
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>v3.1 Scan — TILAKNAGAR + THYROCARE</b>")
    lines.append(f"<b>{date.today()}</b>")
    lines.append("")
    for r in results:
        lines.append(f"<b>{r['symbol']} — {r['pattern']} [{r['timeframe']}]</b>")
        lines.append(f"  Status: {r['status']}  |  Score: {r['score']:.0f}/100  |  R:R: 1:{r['rr']:.2f}")
        lines.append(f"  CMP: {r['cmp']:.2f}  |  BO: {r['breakout']:.2f}  |  Dist: {r['dist_pct']:+.1f}%")
        lines.append(f"  Stop: {r['stop']:.2f} ({r['risk_pct']:.1f}% risk)")
        lines.append(f"  T1: {r['t1']:.2f} ({(r['t1']-r['cmp'])/r['cmp']*100:+.1f}%)  T2: {r['t2']:.2f} ({(r['t2']-r['cmp'])/r['cmp']*100:+.1f}%)")
        lines.append(f"  Sector: {r['sector']} ({r['sector_signal']})")
        lines.append(f"  Vol: {r['vol_ratio']:.1f}x  Day: {r['day_chg']:+.2f}%")
        lines.append(f"  <b>VERDICT: {r['verdict']}</b>")
        lines.append("")
    lines.append("Not financial advice.")
    ok = send_telegram(token, chat_id, "\n".join(lines))
    print(f"\n  [Telegram] {'Sent' if ok else 'Failed'}")
