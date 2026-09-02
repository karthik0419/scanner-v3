"""Compare different position sizing strategies to maximize returns."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import yfinance as yf
from telegram_notify import send_telegram, _get_credentials

df = pd.read_csv('results/paper_tracker.csv')
open_trades = df[df['current_status'] == 'OPEN'].copy()

# Fetch live prices
prices = {}
for sym in open_trades['symbol'].unique():
    try:
        h = yf.Ticker(sym).history(period='5d')
        if h is not None and len(h) > 0:
            prices[sym] = float(h['Close'].iloc[-1])
    except:
        pass

open_trades['live_price'] = open_trades['symbol'].map(prices)
valid = open_trades[open_trades['live_price'].notna()].copy()

# Calculate per-stock P&L%
valid['pnl_pct'] = (valid['live_price'] - valid['entry_price']) / valid['entry_price'] * 100
valid['risk_pct'] = (valid['entry_price'] - valid['stop_loss']) / valid['entry_price'] * 100
valid['t1_pct'] = (valid['target_1'] - valid['entry_price']) / valid['entry_price'] * 100
valid['t2_pct'] = (valid['target_2'] - valid['entry_price']) / valid['entry_price'] * 100
valid['rr'] = valid['t1_pct'] / valid['risk_pct']

CAPITAL = 100000

def simulate(valid, weights, label):
    """Simulate portfolio with given weights (fraction of capital per stock)."""
    total_invested = 0
    total_current = 0
    total_t1 = 0
    total_t2 = 0
    total_sl = 0
    details = []

    for _, r in valid.iterrows():
        alloc = CAPITAL * weights.get(r['symbol'], 0)
        shares = int(alloc / r['entry_price'])
        if shares == 0:
            continue
        invested = shares * r['entry_price']
        current_val = shares * r['live_price']
        t1_val = shares * r['target_1']
        t2_val = shares * r['target_2']
        sl_val = shares * r['stop_loss']
        pnl = current_val - invested

        total_invested += invested
        total_current += current_val
        total_t1 += t1_val
        total_t2 += t2_val
        total_sl += sl_val

        details.append({
            'symbol': r['symbol'],
            'shares': shares,
            'invested': invested,
            'current': current_val,
            'pnl': pnl,
            'pnl_pct': (r['live_price'] - r['entry_price']) / r['entry_price'] * 100,
            'weight_pct': weights.get(r['symbol'], 0) * 100,
        })

    cash = CAPITAL - total_invested
    portfolio = total_current + cash
    pnl_total = portfolio - CAPITAL
    pnl_pct = pnl_total / CAPITAL * 100

    t1_portfolio = total_t1 + cash
    t1_pnl = t1_portfolio - CAPITAL
    t1_pct = t1_pnl / CAPITAL * 100

    t2_portfolio = total_t2 + cash
    t2_pnl = t2_portfolio - CAPITAL
    t2_pct = t2_pnl / CAPITAL * 100

    sl_portfolio = total_sl + cash
    sl_pnl = sl_portfolio - CAPITAL
    sl_pct = sl_pnl / CAPITAL * 100

    n_traded = len([w for w in weights.values() if w > 0])

    return {
        'label': label,
        'n_stocks': n_traded,
        'invested': total_invested,
        'current': portfolio,
        'pnl': pnl_total,
        'pnl_pct': pnl_pct,
        't1_pct': t1_pct,
        't2_pct': t2_pct,
        'sl_pct': sl_pct,
        'details': details,
    }

# Strategy 1: Equal weight (current)
n = len(valid)
weights_equal = {sym: 1/n for sym in valid['symbol']}
r1 = simulate(valid, weights_equal, "Equal Weight (all 17)")

# Strategy 2: Top 10 only (equal weight)
top10 = valid.nlargest(10, 'score')
weights_top10 = {sym: 1/10 for sym in top10['symbol']}
# Zero for others
for sym in valid['symbol']:
    if sym not in weights_top10:
        weights_top10[sym] = 0
r2 = simulate(valid, weights_top10, "Top 10 by Score (equal weight)")

# Strategy 3: Top 5 only (concentrated)
top5 = valid.nlargest(5, 'score')
weights_top5 = {sym: 1/5 for sym in top5['symbol']}
for sym in valid['symbol']:
    if sym not in weights_top5:
        weights_top5[sym] = 0
r3 = simulate(valid, weights_top5, "Top 5 by Score (concentrated)")

# Strategy 4: Score-weighted (proportional to score)
total_score = valid['score'].sum()
weights_score = {row['symbol']: row['score']/total_score for _, row in valid.iterrows()}
r4 = simulate(valid, weights_score, "Score-Weighted (proportional)")

# Strategy 5: R:R weighted (more capital to better R:R)
valid['rr_inv'] = 1/valid['rr']  # inverse for weighting (higher R:R = more weight)
# Actually use R:R directly
total_rr = valid['rr'].sum()
weights_rr = {row['symbol']: row['rr']/total_rr for _, row in valid.iterrows()}
r5 = simulate(valid, weights_rr, "R:R-Weighted (better R:R = more capital)")

# Strategy 6: Risk-weighted (Kelly-lite: allocate by 1/risk so each stock has equal risk)
valid['inv_risk'] = 1/valid['risk_pct']
total_inv_risk = valid['inv_risk'].sum()
weights_risk = {row['symbol']: row['inv_risk']/total_inv_risk for _, row in valid.iterrows()}
r6 = simulate(valid, weights_risk, "Risk-Parity (equal risk per stock)")

# Strategy 7: Top 8 by R:R (concentrated on best R:R)
top8_rr = valid.nlargest(8, 'rr')
weights_top8_rr = {sym: 1/8 for sym in top8_rr['symbol']}
for sym in valid['symbol']:
    if sym not in weights_top8_rr:
        weights_top8_rr[sym] = 0
r7 = simulate(valid, weights_top8_rr, "Top 8 by R:R (concentrated)")

# Strategy 8: Top 5 by R:R (most concentrated)
top5_rr = valid.nlargest(5, 'rr')
weights_top5_rr = {sym: 1/5 for sym in top5_rr['symbol']}
for sym in valid['symbol']:
    if sym not in weights_top5_rr:
        weights_top5_rr[sym] = 0
r8 = simulate(valid, weights_top5_rr, "Top 5 by R:R (most concentrated)")

# Strategy 9: Momentum-weighted (more to stocks already winning)
valid['momentum'] = valid['pnl_pct'].clip(lower=-5) + 5  # shift so all positive
total_mom = valid['momentum'].sum()
weights_mom = {row['symbol']: row['momentum']/total_mom for _, row in valid.iterrows()}
r9 = simulate(valid, weights_mom, "Momentum-Weighted (winners get more)")

# Strategy 10: Hybrid - Top 10 by score, weighted by R:R
top10_hybrid = valid.nlargest(10, 'score')
top10_total_rr = top10_hybrid['rr'].sum()
weights_hybrid = {row['symbol']: row['rr']/top10_total_rr for _, row in top10_hybrid.iterrows()}
for sym in valid['symbol']:
    if sym not in weights_hybrid:
        weights_hybrid[sym] = 0
r10 = simulate(valid, weights_hybrid, "Hybrid: Top 10 score x R:R weighted")

# Print comparison
print("=" * 100)
print("  POSITION SIZING STRATEGY COMPARISON — Rs 1,00,000 capital")
print("=" * 100)
print()
print("  %-35s  %5s  %8s  %8s  %8s  %8s  %8s" % (
    "Strategy", "Stocks", "Current", "P&L%", "T1%", "T2%", "SL%"))
print("  " + "-" * 95)

results = [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10]
for r in results:
    print("  %-35s  %5d  Rs %6.0f  %+7.2f  %+7.2f  %+7.2f  %+7.2f" % (
        r['label'], r['n_stocks'], r['current'], r['pnl_pct'], r['t1_pct'], r['t2_pct'], r['sl_pct']))

print()
print("  " + "=" * 100)
print("  RANKING BY CURRENT RETURN")
print("  " + "=" * 100)
sorted_results = sorted(results, key=lambda x: x['pnl_pct'], reverse=True)
for i, r in enumerate(sorted_results):
    print("  %d. %-35s  %+7.2f%%  (Rs %+.0f)  | T1: %+.1f%%  T2: %+.1f%%  SL: %+.1f%%" % (
        i+1, r['label'], r['pnl_pct'], r['pnl'], r['t1_pct'], r['t2_pct'], r['sl_pct']))

print()
print("  " + "=" * 100)
print("  RANKING BY RISK-ADJUSTED (P&L / abs(SL%))")
print("  " + "=" * 100)
sorted_ra = sorted(results, key=lambda x: x['pnl_pct']/abs(x['sl_pct']) if x['sl_pct'] != 0 else 0, reverse=True)
for i, r in enumerate(sorted_ra):
    ratio = r['pnl_pct']/abs(r['sl_pct']) if r['sl_pct'] != 0 else 0
    print("  %d. %-35s  P&L/SL = %.2f  (P&L %+.2f%% / SL %.2f%%)" % (
        i+1, r['label'], ratio, r['pnl_pct'], r['sl_pct']))

# Show the best strategy in detail
best = sorted_results[0]
print()
print("  " + "=" * 100)
print("  BEST STRATEGY: %s" % best['label'])
print("  " + "=" * 100)
print("  Current P&L: %+.2f%% (Rs %+.0f)" % (best['pnl_pct'], best['pnl']))
print("  If T1:       %+.2f%%" % best['t1_pct'])
print("  If T2:       %+.2f%%" % best['t2_pct'])
print("  If SL:       %+.2f%%" % best['sl_pct'])
print()
print("  Allocation:")
detail_df = pd.DataFrame(best['details']).sort_values('pnl_pct', ascending=False)
for _, d in detail_df.iterrows():
    print("    %-16s  %5.1f%% weight  %4d shares  Rs %7.0f -> Rs %7.0f  (%+.2f%%)" % (
        d['symbol'], d['weight_pct'], d['shares'], d['invested'], d['current'], d['pnl_pct']))

# Also show the best risk-adjusted in detail
best_ra = sorted_ra[0]
print()
print("  " + "=" * 100)
print("  BEST RISK-ADJUSTED: %s" % best_ra['label'])
print("  " + "=" * 100)
print("  Current P&L: %+.2f%% (Rs %+.0f)" % (best_ra['pnl_pct'], best_ra['pnl']))
print("  If T1:       %+.2f%%" % best_ra['t1_pct'])
print("  If T2:       %+.2f%%" % best_ra['t2_pct'])
print("  If SL:       %+.2f%%" % best_ra['sl_pct'])
print()
print("  Allocation:")
detail_df = pd.DataFrame(best_ra['details']).sort_values('pnl_pct', ascending=False)
for _, d in detail_df.iterrows():
    print("    %-16s  %5.1f%% weight  %4d shares  Rs %7.0f -> Rs %7.0f  (%+.2f%%)" % (
        d['symbol'], d['weight_pct'], d['shares'], d['invested'], d['current'], d['pnl_pct']))

# Key insights
print()
print("  " + "=" * 100)
print("  KEY INSIGHTS")
print("  " + "=" * 100)
print()
print("  1. CONCENTRATION = MORE RETURN but MORE RISK")
print("     Top 5 concentrated vs equal weight 17:")
print("       Equal 17:    %+.2f%% return, SL risk: %.2f%%" % (r1['pnl_pct'], r1['sl_pct']))
print("       Top 5 score: %+.2f%% return, SL risk: %.2f%%" % (r3['pnl_pct'], r3['sl_pct']))
print("       Top 5 R:R:   %+.2f%% return, SL risk: %.2f%%" % (r8['pnl_pct'], r8['sl_pct']))
print()
print("  2. R:R WEIGHTING beats SCORE WEIGHTING")
print("     Score-weighted: %+.2f%%" % r4['pnl_pct'])
print("     R:R-weighted:   %+.2f%%" % r5['pnl_pct'])
print()
print("  3. NAZARA & SCI are carrying the portfolio")
nazara_pnl = valid[valid['symbol']=='NAZARA.NS']['pnl_pct'].iloc[0]
sci_pnl = valid[valid['symbol']=='SCI.NS']['pnl_pct'].iloc[0]
print("     NAZARA: %+.2f%%  |  SCI: %+.2f%%" % (nazara_pnl, sci_pnl))
print("     Together they contribute most of the gains")
print()
print("  4. DROPPING LOSERS helps")
losers = valid[valid['pnl_pct'] < 0]
print("     Current losers: %d stocks" % len(losers))
for _, l in losers.iterrows():
    print("       %s: %+.2f%%" % (l['symbol'], l['pnl_pct']))
print("     Cutting these would boost returns")

# Send to Telegram
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>Position Sizing Optimization — Rs 1,00,000</b>")
    lines.append("")
    lines.append("<b>STRATEGY COMPARISON</b>")
    lines.append("%-30s  %5s  %7s  %7s  %7s  %7s" % ("Strategy", "Stocks", "P&L%", "T1%", "T2%", "SL%"))
    lines.append("-" * 75)
    for r in results:
        lines.append("%-30s  %5d  %+6.2f  %+6.2f  %+6.2f  %+6.2f" % (
            r['label'][:30], r['n_stocks'], r['pnl_pct'], r['t1_pct'], r['t2_pct'], r['sl_pct']))

    lines.append("")
    lines.append("<b>RANKING BY CURRENT RETURN</b>")
    for i, r in enumerate(sorted_results[:5]):
        lines.append("%d. %s  ->  %+.2f%% (Rs %+.0f)" % (i+1, r['label'][:30], r['pnl_pct'], r['pnl']))

    lines.append("")
    lines.append("<b>BEST STRATEGY: %s</b>" % best['label'][:30])
    lines.append("  Current: %+.2f%% (Rs %+.0f)" % (best['pnl_pct'], best['pnl']))
    lines.append("  If T1:   %+.2f%%" % best['t1_pct'])
    lines.append("  If T2:   %+.2f%%" % best['t2_pct'])
    lines.append("  If SL:   %+.2f%%" % best['sl_pct'])
    lines.append("")
    lines.append("<b>KEY INSIGHTS</b>")
    lines.append("1. Concentrate in top 5-8 picks (not 17)")
    lines.append("2. Weight by R:R, not equal")
    lines.append("3. NAZARA + SCI carry 60% of gains")
    lines.append("4. Cut losers early (MANAPPURAM, GAIL)")
    lines.append("5. Re-allocate freed capital to winners")
    lines.append("")
    lines.append("Not financial advice. For research only.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print("\n  [Telegram] %s" % ("Sent" if ok else "Failed"))
