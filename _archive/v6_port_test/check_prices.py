import yfinance as yf

stocks = {
    "VEDL": "VEDL.NS",
    "SAIL": "SAIL.NS",
    "MANAPPURAM": "MANAPPURAM.NS",
    "FEDERALBNK": "FEDERALBNK.NS",
    "RECLTD": "RECLTD.NS",
    "SCI": "SCI.NS",
    "COMSYN": "COMSYN.NS",
}

print("EOD PRICE CHECK")
print("-" * 60)
for name, sym in stocks.items():
    try:
        t = yf.Ticker(sym)
        h = t.history(period="5d")
        if h.empty:
            print(f"  {name:<15} no data")
            continue
        close = float(h["Close"].iloc[-1])
        prev = float(h["Close"].iloc[-2]) if len(h) > 1 else close
        chg = (close - prev) / prev * 100
        print(f"  {name:<15} Rs.{close:>8.2f}  ({chg:+.2f}%)")
    except Exception as e:
        print(f"  {name:<15} error: {e}")
