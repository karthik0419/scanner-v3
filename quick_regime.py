import yfinance as yf
n = yf.download('^NSEI', period='1y', progress=False)
n['s50'] = n['Close'].rolling(50).mean()
n['s200'] = n['Close'].rolling(200).mean()
c = float(n['Close'].iloc[-1])
s50 = float(n['s50'].iloc[-1])
s200 = float(n['s200'].iloc[-1])
print(f'Nifty: {c:.0f}')
print(f'SMA50: {s50:.0f}')
print(f'SMA200: {s200:.0f}')
regime = "BULL" if c > s50 and c > s200 and s50 > s200 else "BEAR/CHOPPY"
print(f'Regime: {regime}')
if regime == "BEAR/CHOPPY":
    print("\n🛑 MARKET NOT SUPPORTIVE - This is why stocks aren't working!")
