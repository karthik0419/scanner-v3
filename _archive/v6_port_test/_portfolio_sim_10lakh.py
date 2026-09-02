"""Calculate returns if Rs 10,00,000 invested evenly across all open positions."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import yfinance as yf
from datetime import datetime
from telegram_notify import send_telegram, _get_credentials

df = pd.read_csv('results/paper_tracker.csv')
open_trades = df[df['current_status'] == 'OPEN'].copy()

# Fetch live prices
print("Fetching live prices...")
prices = {}
for sym in open_trades['symbol'].unique():
    try:
        h = yf.Ticker(sym).history(period='5d')
        if h is not None and len(h) > 0:
            prices[sym] = float(h['Close'].iloc[-1])
    except:
        pass

open_trades['live_price'] = open_trades['symbol'].map(prices)

# Remove stocks with no live price (TATAMOTORS)
valid = open_trades[open_trades['live_price'].notna()].copy()

TOTAL_CAPITAL = 100000  # Rs 1 lakh
n_stocks = len(valid)
per_stock = TOTAL_CAPITAL / n_stocks

print()
print("=" * 80)
print("  PORTFOLIO SIMULATION — Rs 10,00,000 invested evenly across %d open positions" % n_stocks)
print("=" * 80)
print()
print("  Capital: Rs %s" % format(TOTAL_CAPITAL, ',.0f'))
print("  Positions: %d" % n_stocks)
print("  Allocation per stock: Rs %s" % format(per_stock, ',.2f'))
print()

# Calculate shares (integer), invested, current value, P&L
results = []
total_invested = 0
total_current = 0

for _, r in valid.iterrows():
    entry = r['entry_price']
    live = r['live_price']
    # Buy integer shares at entry price
    shares = int(per_stock / entry)
    invested = shares * entry
    current_val = shares * live
    pnl = current_val - invested
    pnl_pct = (live - entry) / entry * 100
    # Remaining cash from rounding
    cash_left = per_stock - invested

    total_invested += invested
    total_current += current_val

    results.append({
        'symbol': r['symbol'],
        'pattern': r['pattern'],
        'entry': entry,
        'live': live,
        'shares': shares,
        'invested': invested,
        'current_val': current_val,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'sl': r['stop_loss'],
        't1': r['target_1'],
        't2': r['target_2'],
        'days_held': r['days_held'],
        'cash_left': cash_left,
    })

rdf = pd.DataFrame(results).sort_values('pnl_pct', ascending=False)

# Total cash left from rounding
total_cash_left = sum(r['cash_left'] for r in results)
total_pnl = total_current - total_invested
total_pnl_pct = (total_current - total_invested) / total_invested * 100
portfolio_value = total_current + total_cash_left
total_return_pct = (portfolio_value - TOTAL_CAPITAL) / TOTAL_CAPITAL * 100

# Print per-stock breakdown
print("  %-16s  %-20s  %6s  %6s  %6s  %10s  %10s  %10s  %7s  %5s" % (
    "Symbol", "Pattern", "Entry", "Live", "Shares", "Invested", "Current", "P&L Rs", "P&L%", "Days"))
print("  " + "-" * 110)

for _, r in rdf.iterrows():
    print("  %-16s  %-20s  %6.2f  %6.2f  %6d  Rs %8.0f  Rs %8.0f  %+.0f  %+6.2f%%  %3d" % (
        r['symbol'], r['pattern'][:20], r['entry'], r['live'], r['shares'],
        r['invested'], r['current_val'], r['pnl'], r['pnl_pct'], r['days_held']))

print("  " + "-" * 110)
print()
print("  PORTFOLIO SUMMARY")
print("  " + "=" * 60)
print("  Total capital:       Rs %s" % format(TOTAL_CAPITAL, ',.0f'))
print("  Total invested:      Rs %s  (shares bought)" % format(total_invested, ',.0f'))
print("  Cash left (rounding):Rs %s" % format(total_cash_left, ',.0f'))
print("  Current value:       Rs %s  (shares at live price)" % format(total_current, ',.0f'))
print("  Total P&L:           Rs %+.0f" % total_pnl)
print("  Return on invested:  %+.2f%%" % total_pnl_pct)
print("  Return on capital:   %+.2f%%" % total_return_pct)
print("  Portfolio value:     Rs %s" % format(portfolio_value, ',.0f'))
print()

# Winners and losers
winners = rdf[rdf['pnl'] > 0]
losers = rdf[rdf['pnl'] < 0]
print("  Winners: %d/%d  |  Losers: %d/%d" % (len(winners), n_stocks, len(losers), n_stocks))
print("  Best:  %s  %+6.2f%%  (Rs %+.0f)" % (rdf.iloc[0]['symbol'], rdf.iloc[0]['pnl_pct'], rdf.iloc[0]['pnl']))
print("  Worst: %s  %+6.2f%%  (Rs %+.0f)" % (rdf.iloc[-1]['symbol'], rdf.iloc[-1]['pnl_pct'], rdf.iloc[-1]['pnl']))
print()

# If all hit T1
print("  " + "=" * 60)
print("  IF ALL HIT TARGET 1:")
t1_value = 0
for _, r in rdf.iterrows():
    t1_value += r['shares'] * r['t1']
t1_pnl = t1_value - total_invested
t1_pct = (t1_value - total_invested) / total_invested * 100
print("  Portfolio value at T1:  Rs %s" % format(t1_value, ',.0f'))
print("  P&L at T1:              Rs %+.0f  (%+.2f%%)" % (t1_pnl, t1_pct))
print()

# If all hit T2
print("  IF ALL HIT TARGET 2:")
t2_value = 0
for _, r in rdf.iterrows():
    t2_value += r['shares'] * r['t2']
t2_pnl = t2_value - total_invested
t2_pct = (t2_value - total_invested) / total_invested * 100
print("  Portfolio value at T2:  Rs %s" % format(t2_value, ',.0f'))
print("  P&L at T2:              Rs %+.0f  (%+.2f%%)" % (t2_pnl, t2_pct))
print()

# If all hit SL
print("  IF ALL HIT STOP LOSS (worst case):")
sl_value = 0
for _, r in rdf.iterrows():
    sl_value += r['shares'] * r['sl']
sl_pnl = sl_value - total_invested
sl_pct = (sl_value - total_invested) / total_invested * 100
print("  Portfolio value at SL:  Rs %s" % format(sl_value, ',.0f'))
print("  P&L at SL:              Rs %+.0f  (%+.2f%%)" % (sl_pnl, sl_pct))
print()

# Days held
avg_days = rdf['days_held'].mean()
print("  Avg days held: %.1f days" % avg_days)
print("  Annualized return: %+.1f%%" % (total_return_pct / avg_days * 252))
print()

# Comparison
print("  " + "=" * 60)
print("  COMPARISON")
print("  " + "=" * 60)
print("  Bank FD (7%% annual, %d days): Rs %s" % (int(avg_days), format(TOTAL_CAPITAL * (1 + 0.07 * avg_days / 365), ',.0f')))
print("  Current portfolio:           Rs %s" % format(portfolio_value, ',.0f'))
print("  Difference:                  Rs %+.0f" % (portfolio_value - TOTAL_CAPITAL * (1 + 0.07 * avg_days / 365)))
print()

# Send to Telegram
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>Portfolio Simulation — Rs 10,00,000 evenly across all open positions</b>")
    lines.append("<b>Date: 2026-08-04 | %d open positions</b>" % n_stocks)
    lines.append("")
    lines.append("Capital: Rs 10,00,000")
    lines.append("Per stock: Rs %.0f" % per_stock)
    lines.append("")
    lines.append("<b>PER-STOCK BREAKDOWN</b>")
    lines.append("%-14s  %6s  %6s  %5s  %9s  %9s  %+7s" % ("Symbol", "Entry", "Live", "Qty", "Invested", "Current", "P&L%"))
    for _, r in rdf.iterrows():
        lines.append("%-14s  %6.2f  %6.2f  %5d  Rs %7.0f  Rs %7.0f  %+.2f%%" % (
            r['symbol'], r['entry'], r['live'], r['shares'], r['invested'], r['current_val'], r['pnl_pct']))

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("<b>PORTFOLIO SUMMARY</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("Capital:       Rs %s" % format(TOTAL_CAPITAL, ',.0f'))
    lines.append("Invested:      Rs %s" % format(total_invested, ',.0f'))
    lines.append("Current value: Rs %s" % format(total_current, ',.0f'))
    lines.append("Cash left:     Rs %s" % format(total_cash_left, ',.0f'))
    lines.append("Total P&L:     Rs %+.0f" % total_pnl)
    lines.append("Return:        %+.2f%%" % total_return_pct)
    lines.append("Winners:       %d/%d" % (len(winners), n_stocks))
    lines.append("Avg days:      %.1f" % avg_days)
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("<b>SCENARIOS</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("If ALL hit T1: Rs %s (%+.2f%%)" % (format(t1_value, ',.0f'), t1_pct))
    lines.append("If ALL hit T2: Rs %s (%+.2f%%)" % (format(t2_value, ',.0f'), t2_pct))
    lines.append("If ALL hit SL: Rs %s (%+.2f%%)" % (format(sl_value, ',.0f'), sl_pct))
    lines.append("")
    lines.append("Best:  %s %+6.2f%% (Rs %+.0f)" % (rdf.iloc[0]['symbol'], rdf.iloc[0]['pnl_pct'], rdf.iloc[0]['pnl']))
    lines.append("Worst: %s %+6.2f%% (Rs %+.0f)" % (rdf.iloc[-1]['symbol'], rdf.iloc[-1]['pnl_pct'], rdf.iloc[-1]['pnl']))
    lines.append("")
    lines.append("Bank FD (%d days @7%%): Rs %s" % (int(avg_days), format(TOTAL_CAPITAL * (1 + 0.07 * avg_days / 365), ',.0f')))
    lines.append("Portfolio:             Rs %s" % format(portfolio_value, ',.0f'))
    lines.append("Alpha vs FD:           Rs %+.0f" % (portfolio_value - TOTAL_CAPITAL * (1 + 0.07 * avg_days / 365)))
    lines.append("")
    lines.append("Not financial advice. Paper trades for research.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print("\n  [Telegram] %s" % ("Sent" if ok else "Failed"))
