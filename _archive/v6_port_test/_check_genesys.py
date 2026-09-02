"""Quick check on GENESYS.NS — is it a valid setup?"""
import yfinance as yf

t = yf.Ticker('GENESYS.NS')
h = t.history(period='6mo')
if h.index.tz:
    h.index = h.index.tz_localize(None)

print(f"GENESYS.NS — Technology sector")
print(f"Current: Rs {h['Close'].iloc[-1]:.2f}")
print(f"50-day high: Rs {h['High'].rolling(50).max().iloc[-1]:.2f}")
print(f"50-day SMA: Rs {h['Close'].rolling(50).mean().iloc[-1]:.2f}")
print(f"20-day SMA: Rs {h['Close'].rolling(20).mean().iloc[-1]:.2f}")
print(f"Volume avg 20d: {h['Volume'].rolling(20).mean().iloc[-1]:.0f}")
lookback = min(126, len(h)-1)
print(f"6-month return: {(h['Close'].iloc[-1]/h['Close'].iloc[-lookback]-1)*100:.1f}%")
print()
print("Last 10 days:")
print(h[['Open','High','Low','Close','Volume']].tail(10).to_string())
print()

# Check if it was in any scan
import os
for f in os.listdir('results'):
    if f.startswith('v3_') and f.endswith('_all.csv'):
        with open(f'results/{f}') as fh:
            if 'GENESYS' in fh.read():
                print(f"Found in: {f}")
