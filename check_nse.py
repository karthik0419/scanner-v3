from jugaad_data.nse import quote_today, NSEQuote
import datetime

stocks = ["VEDL", "SAIL", "MANAPPURAM", "FEDERALBNK", "RECLTD", "SCI", "COMSYN"]

print("EOD PRICE CHECK (NSE)")
print("-" * 60)
for sym in stocks:
    try:
        q = NSEQuote().quote(symbol=sym)
        print(f"  {sym:<15} Rs.{q['lastPrice']:>8.2f}  ({q['pctChange']:+.2f}%)")
    except Exception as e:
        print(f"  {sym:<15} error: {str(e)[:50]}")
