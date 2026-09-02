import yfinance as yf
import numpy as np

t = yf.Ticker('GENESYS.NS')
h = t.history(period='6mo')
if h.index.tz:
    h.index = h.index.tz_localize(None)

breakout_level = 293.09
original_entry = 300.55
original_stop = 276.51
t1 = 350.11
t2 = 388.13
stop_date = '2026-07-29'

today = h.index[-1]
today_high = float(h['High'].iloc[-1])
today_close = float(h['Close'].iloc[-1])
today_low = float(h['Low'].iloc[-1])
today_open = float(h['Open'].iloc[-1])

stop_idx = None
for i, idx in enumerate(h.index):
    if idx.strftime('%Y-%m-%d') == stop_date:
        stop_idx = i
        break

days_since_stop = (today - h.index[stop_idx]).days if stop_idx else 999

re_entry = today_close
re_stop = breakout_level * 0.98
re_stop_pct = (re_entry - re_stop) / re_entry * 100

vol_today = float(h['Volume'].iloc[-1])
vol_avg_20 = float(h['Volume'].rolling(20).mean().iloc[-1])
vol_ratio = vol_today / vol_avg_20

tr = np.maximum(h['High'] - h['Low'], np.maximum((h['High'] - h['Close'].shift(1)).abs(), (h['Low'] - h['Close'].shift(1)).abs()))
atr = tr.rolling(14).mean().iloc[-1]

all_conditions = (today_high >= breakout_level) and (days_since_stop <= 30)

lines = []
lines.append("============================================================")
lines.append("  GENESYS.NS - RE-ENTRY CHECK")
lines.append("============================================================")
lines.append("")
lines.append("ORIGINAL TRADE (Jul 27 scan):")
lines.append("  Pattern: Double Bottom BREAKOUT")
lines.append("  Entry:   Rs 300.55")
lines.append("  Stop:    Rs 276.51 (hit on Jul 29)")
lines.append("  Result:  -8.0%% loss")
lines.append("")
lines.append("RE-ENTRY CONDITIONS (v3.1 rules):")
lines.append("  1. Stock hit SL?              YES (Jul 29, low 272.25 < 276.51)")
lines.append("  2. Recovered above breakout?  %s (today high Rs %.2f %s breakout Rs %.2f)" % (
    "YES" if today_high >= breakout_level else "NO", today_high, ">" if today_high >= breakout_level else "<", breakout_level))
lines.append("  3. Within 30 days of SL?      %s (%d days since stop)" % ("YES" if days_since_stop <= 30 else "NO", days_since_stop))
lines.append("")
lines.append("RE-ENTRY TRADE LEVELS:")
lines.append("  Re-entry price: Rs %.2f (today close)" % re_entry)
lines.append("  New stop:       Rs %.2f (2%% below breakout 293.09)" % re_stop)
lines.append("  Stop risk:      %.2f%%" % re_stop_pct)
lines.append("  Target 1:       Rs 350.11 (+%.2f%%)" % ((t1 - re_entry) / re_entry * 100))
lines.append("  Target 2:       Rs 388.13 (+%.2f%%)" % ((t2 - re_entry) / re_entry * 100))
lines.append("  R:R to T1:      1:%.2f" % ((t1 - re_entry) / (re_entry - re_stop)))
lines.append("  R:R to T2:      1:%.2f" % ((t2 - re_entry) / (re_entry - re_stop)))
lines.append("")
lines.append("VOLUME CHECK:")
lines.append("  Today volume:  %d" % int(vol_today))
lines.append("  20-day avg:    %d" % int(vol_avg_20))
lines.append("  Ratio:         %.2fx %s" % (vol_ratio, "(STRONG)" if vol_ratio > 1.5 else "(weak)"))
lines.append("")
lines.append("ATR(14): Rs %.2f (%.2f%% of price)" % (atr, atr / re_entry * 100))
lines.append("")
lines.append("RISK ASSESSMENT:")
lines.append("  Original loss: -8.0%% (Rs %.2f/share)" % (original_entry - original_stop))
lines.append("  Re-entry risk: -%.2f%% (Rs %.2f/share)" % (re_stop_pct, re_entry - re_stop))
lines.append("  Re-entry is TIGHTER (%.2f%% vs 8.0%%)" % re_stop_pct)
lines.append("")
lines.append("============================================================")
if all_conditions:
    lines.append("  VERDICT: RE-ENTRY APPROVED")
    lines.append("============================================================")
    lines.append("")
    lines.append("  All 3 conditions met:")
    lines.append("  1. Stopped out Jul 29")
    lines.append("  2. Today high Rs %.2f > breakout Rs 293.09" % today_high)
    lines.append("  3. %d days since stop (within 30-day window)" % days_since_stop)
    lines.append("")
    lines.append("  RECOMMENDED TRADE:")
    lines.append("    Enter: Rs %.2f (today close or tomorrow open)" % re_entry)
    lines.append("    Stop:  Rs %.2f (tight 2%% stop)" % re_stop)
    lines.append("    T1:    Rs 350.11 (+%.1f%%)" % ((t1 - re_entry) / re_entry * 100))
    lines.append("    T2:    Rs 388.13 (+%.1f%%)" % ((t2 - re_entry) / re_entry * 100))
    lines.append("    R:R:   1:%.2f to T1" % ((t1 - re_entry) / (re_entry - re_stop)))
    lines.append("")
    lines.append("  Volume today: %.2fx avg (%s)" % (vol_ratio, "STRONG confirmation" if vol_ratio > 1.5 else "weak"))
else:
    lines.append("  VERDICT: RE-ENTRY NOT APPROVED")
    lines.append("============================================================")

output = "\n".join(lines)
with open("_reentry_result.txt", "w", encoding="utf-8") as f:
    f.write(output)
print(output)
