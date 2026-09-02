from jugaad_data.nse import NSELive
l = NSELive()
stocks = ["VEDL", "SAIL", "MANAPPURAM", "FEDERALBNK", "RECLTD", "SCI", "COMSYN"]

print("EOD PRICE CHECK (NSE Live)")
print("-" * 60)
for sym in stocks:
    try:
        q = l.stock_quote(sym)
        lp = q.get("priceInfo", {}).get("lastPrice", "N/A")
        chg = q.get("priceInfo", {}).get("pChange", 0)
        print(f"  {sym:<15} Rs.{lp:>8}  ({chg:+.2f}%)")
    except Exception as e:
        print(f"  {sym:<15} error: {str(e)[:60]}")
