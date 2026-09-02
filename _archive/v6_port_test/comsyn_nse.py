from jugaad_data.nse import NSELive
l = NSELive()
try:
    q = l.stock_quote("COMSYN")
    p = q.get("priceInfo", {})
    close = p.get("lastPrice", 0)
    chg = p.get("pChange", 0)
    high = p.get("intraDayHighLow", {}).get("max", 0)
    low = p.get("intraDayHighLow", {}).get("min", 0)
    print(f"COMSYN — NSE LIVE")
    print(f"  Close: Rs.{close}  ({chg}%)")
    print(f"  Day High: Rs.{high}")
    print(f"  Day Low: Rs.{low}")
except Exception as e:
    print(f"NSE Live error: {e}")

# Also check with historical data
from jugaad_data.nse import NSEHistory
from datetime import date, timedelta
h = NSEHistory()
end = date.today()
start = end - timedelta(days=30)
try:
    df = h.stock_history("COMSYN", start, end)
    if df is not None and len(df) > 0:
        close = float(df["CH_CLOSING_PRICE"].iloc[-1])
        high = float(df["CH_HIGH_PRICE"].max())
        low = float(df["CH_LOW_PRICE"].min())
        print(f"\nCOMSYN — NSE Historical (last 30 days)")
        print(f"  Latest close: Rs.{close:.2f}")
        print(f"  30-day high:  Rs.{high:.2f}")
        print(f"  30-day low:   Rs.{low:.2f}")
        
        breakout = 224.60
        dist = (breakout - close) / close * 100
        watch = breakout * 0.90
        near = breakout * 0.95
        
        print(f"\n  Breakout:  Rs.{breakout}")
        print(f"  Distance:  {dist:.1f}% below breakout")
        
        if close >= breakout:
            print(f"  STATUS: BREAKOUT!")
        elif close >= near:
            print(f"  STATUS: NEAR (set alert at {breakout})")
        elif close >= watch:
            print(f"  STATUS: WATCH ({(breakout-close)/close*100:.1f}% to go)")
        else:
            print(f"  STATUS: FILTERED (too far)")
    else:
        print("No historical data")
except Exception as e:
    print(f"NSE History error: {e}")
