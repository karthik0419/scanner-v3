import yfinance as yf

t = yf.Ticker('GENESYS.NS')
h = t.history(period='6mo')
if h.index.tz:
    h.index = h.index.tz_localize(None)

lines = []
lines.append("GENESYS.NS - Technology")
lines.append("Current: Rs %.2f" % h['Close'].iloc[-1])
lines.append("50-day high: Rs %.2f" % h['High'].rolling(50).max().iloc[-1])
lines.append("50-day SMA: Rs %.2f" % h['Close'].rolling(50).mean().iloc[-1])
lines.append("20-day SMA: Rs %.2f" % h['Close'].rolling(20).mean().iloc[-1])
lines.append("Vol avg 20d: %.0f" % h['Volume'].rolling(20).mean().iloc[-1])
lb = min(126, len(h) - 1)
lines.append("6mo return: %.1f%%" % ((h['Close'].iloc[-1] / h['Close'].iloc[-lb] - 1) * 100))
lines.append("")
lines.append("Last 10 days:")
for idx, row in h[['Open', 'High', 'Low', 'Close', 'Volume']].tail(10).iterrows():
    lines.append("  %s  O=%.2f H=%.2f L=%.2f C=%.2f V=%d" % (
        idx.strftime("%Y-%m-%d"), row['Open'], row['High'], row['Low'], row['Close'], int(row['Volume'])))

# Check if in any scan
import os
lines.append("")
lines.append("Scan history:")
found = False
for fn in sorted(os.listdir('results')):
    if fn.startswith('v3_') and fn.endswith('_all.csv'):
        with open('results/' + fn) as fh:
            if 'GENESYS' in fh.read():
                lines.append("  Found in: " + fn)
                found = True
if not found:
    lines.append("  NOT found in any v3 scan")

# Check universe files
lines.append("")
for uf in ['backbone50.txt', 'nifty200.txt', 'nifty500.txt']:
    if os.path.exists(uf):
        with open(uf) as fh:
            if 'GENESYS' in fh.read():
                lines.append("  In universe: " + uf)

with open('_genesys_clean.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
