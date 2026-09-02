import yfinance as yf
t = yf.Ticker("VEDL.NS")
h = t.history(period="5d")
close = round(float(h["Close"].iloc[-1]), 2)
low = round(float(h["Low"].iloc[-1]), 2)
high = round(float(h["High"].iloc[-1]), 2)
print("VEDL close:", close, "| low:", low, "| high:", high)

# Live trade calc
entry = 263.40
sl = 245.00
target = 330.00
qty = 80
pnl = (close - entry) * qty
pnl_pct = (close - entry) / entry * 100
print("Your entry:", entry, "| SL:", sl, "| Target:", target)
print("Current P&L: Rs.", round(pnl, 2), "(", round(pnl_pct, 2), "%)")
print("Distance to SL:", round((close - sl) / close * 100, 1), "%")
print("Distance to target:", round((target - close) / close * 100, 1), "%")
