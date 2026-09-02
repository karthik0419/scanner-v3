"""Check GENESYS trade trajectory from Jul 27 breakout signal."""
import yfinance as yf

t = yf.Ticker('GENESYS.NS')
h = t.history(period='3mo')
if h.index.tz:
    h.index = h.index.tz_localize(None)

# From Jul 27 scan: Double Bottom BREAKOUT
# breakout=293.09, stop=276.51, T1=350.11, T2=388.13, CMP=300.55, score=80.7
entry = 300.55  # CMP at scan (BREAKOUT = enter at CMP)
stop = 276.51
t1 = 350.11
t2 = 388.13

print("GENESYS.NS — Double Bottom BREAKOUT (Jul 27 scan)")
print("  Score: 80.7 (high conviction)")
print("  Entry: Rs 300.55 (CMP at scan)")
print("  Stop:  Rs 276.51 (risk: 8.0%)")
print("  T1:    Rs 350.11 (upside: +16.5%)")
print("  T2:    Rs 388.13 (upside: +29.1%)")
print("  R:R:   2.06")
print()

# Trace the trade from Jul 27 forward
print("Trade trajectory:")
print("  Date         Open     High     Low      Close    Status")
started = False
stopped = False
hit_t1 = False
hit_t2 = False

for idx, row in h.iterrows():
    d = idx.strftime('%Y-%m-%d')
    if d < '2026-07-27':
        continue
    if not started:
        started = True

    status = ""
    if not stopped and not hit_t1:
        if row['Low'] <= stop:
            status = "*** STOP HIT ***"
            stopped = True
        elif row['High'] >= t1:
            status = "*** T1 HIT ***"
            hit_t1 = True
        elif row['High'] >= t2:
            status = "*** T2 HIT ***"
            hit_t2 = True
    elif hit_t1 and not hit_t2:
        if row['Low'] <= stop:
            status = "*** STOP HIT (after T1) ***"
            stopped = True
        elif row['High'] >= t2:
            status = "*** T2 HIT ***"
            hit_t2 = True

    pnl = (row['Close'] - entry) / entry * 100
    print("  %s  %7.2f  %7.2f  %7.2f  %7.2f  %+.2f%%  %s" % (
        d, row['Open'], row['High'], row['Low'], row['Close'], pnl, status))

print()
if stopped:
    print("  RESULT: STOPPED OUT at Rs 276.51 (-8.0%)")
elif hit_t2:
    print("  RESULT: T2 HIT at Rs 388.13 (+29.1%)")
elif hit_t1:
    print("  RESULT: T1 HIT, still holding for T2")
else:
    current = h['Close'].iloc[-1]
    pnl = (current - entry) / entry * 100
    print("  RESULT: Still open, current P&L: %+.2f%% (Rs %.2f)" % (pnl, current))
