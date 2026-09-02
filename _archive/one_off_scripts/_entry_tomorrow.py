"""List all stocks that broke out today -> entry for tomorrow."""
import pandas as pd
import yfinance as yf

df = pd.read_csv('results/paper_tracker.csv')

# Waiting breakout stocks that are NOW above breakout level
waiting = df[df['current_status'] == 'WAITING_BREAKOUT'].copy()

# Fetch live prices
symbols = waiting['symbol'].unique().tolist()
prices = {}
for sym in symbols:
    try:
        h = yf.Ticker(sym).history(period='5d')
        if h is not None and len(h) > 0:
            prices[sym] = {
                'close': float(h['Close'].iloc[-1]),
                'high': float(h['High'].iloc[-1]),
                'low': float(h['Low'].iloc[-1]),
                'open': float(h['Open'].iloc[-1]),
            }
    except:
        pass

waiting['live_close'] = waiting['symbol'].map(lambda s: prices.get(s, {}).get('close'))
waiting['live_high'] = waiting['symbol'].map(lambda s: prices.get(s, {}).get('high'))

# Broke out = live close > breakout level
waiting['above_breakout'] = waiting['live_close'] > waiting['breakout_level']
waiting['dist_pct'] = ((waiting['live_close'] - waiting['breakout_level']) / waiting['breakout_level']) * 100

broke_out = waiting[waiting['above_breakout'] == True].sort_values('dist_pct', ascending=False)
near = waiting[(waiting['above_breakout'] == False) & (waiting['dist_pct'] > -3)].sort_values('dist_pct', ascending=False)

lines = []
lines.append("=" * 70)
lines.append("  STOCKS TO ENTER TOMORROW (broke out today)")
lines.append("=" * 70)
lines.append("")
lines.append("These were WAITING_BREAKOUT (NEAR picks). They broke above")
lines.append("their breakout level today -> ENTER TOMORROW at open.")
lines.append("")
lines.append("%-16s  %-18s  %8s  %8s  %8s  %8s  %8s  %8s  %5s  %5s" % (
    "Symbol", "Pattern", "Breakout", "Entry", "Stop", "T1", "T2", "Live", "Risk%", "R:R"))
lines.append("-" * 110)

for _, r in broke_out.iterrows():
    # Entry = breakout level (that's where you enter)
    entry = r['breakout_level']
    stop = r['stop_loss']
    t1 = r['target_1']
    t2 = r['target_2']
    live = r['live_close']
    risk = (entry - stop) / entry * 100
    rr = (t1 - entry) / (entry - stop)
    lines.append("%-16s  %-18s  Rs %6.2f  Rs %6.2f  Rs %6.2f  Rs %6.2f  Rs %6.2f  Rs %6.2f  %5.1f  %5.2f" % (
        r['symbol'], r['pattern'], r['breakout_level'], entry, stop, t1, t2, live, risk, rr))

lines.append("")
lines.append("=" * 70)
lines.append("  NEAR BREAKOUT (watch closely, may trigger tomorrow)")
lines.append("=" * 70)
lines.append("")
for _, r in near.iterrows():
    entry = r['breakout_level']
    stop = r['stop_loss']
    t1 = r['target_1']
    t2 = r['target_2']
    live = r['live_close']
    risk = (entry - stop) / entry * 100
    rr = (t1 - entry) / (entry - stop)
    lines.append("%-16s  %-18s  Rs %6.2f  Rs %6.2f  Rs %6.2f  Rs %6.2f  Rs %6.2f  Rs %6.2f  %5.1f  %5.2f  (%+.2f%% from breakout)" % (
        r['symbol'], r['pattern'], r['breakout_level'], entry, stop, t1, t2, live, risk, rr, r['dist_pct']))

lines.append("")
lines.append("=" * 70)
lines.append("  ENTRY INSTRUCTIONS FOR TOMORROW")
lines.append("=" * 70)
lines.append("")
lines.append("BROKE OUT TODAY (enter at open):")
for _, r in broke_out.iterrows():
    lines.append("  %s -> Buy at/above Rs %.2f  |  SL: Rs %.2f  |  T1: Rs %.2f  |  T2: Rs %.2f  |  Risk: %.1f%%" % (
        r['symbol'], r['breakout_level'], r['stop_loss'], r['target_1'], r['target_2'],
        (r['breakout_level'] - r['stop_loss']) / r['breakout_level'] * 100))
lines.append("")
lines.append("WATCH (enter only if breaks above breakout):")
for _, r in near.iterrows():
    lines.append("  %s -> Buy if crosses Rs %.2f  |  SL: Rs %.2f  |  T1: Rs %.2f  |  T2: Rs %.2f" % (
        r['symbol'], r['breakout_level'], r['stop_loss'], r['target_1'], r['target_2']))

output = "\n".join(lines)
with open("_entry_tomorrow.txt", "w", encoding="utf-8") as f:
    f.write(output)
print(output)
