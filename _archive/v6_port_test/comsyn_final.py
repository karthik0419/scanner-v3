from jugaad_data.nse import stock_df
from datetime import date, timedelta

end = date.today()
start = end - timedelta(days=30)

try:
    df = stock_df(symbol="COMSYN", from_date=start, to_date=end, series="EQ")
    if df is not None and len(df) > 0:
        close = float(df["CH_CLOSING_PRICE"].iloc[-1])
        high = float(df["CH_TRADE_HIGH_PRICE"].max())
        low = float(df["CH_TRADE_LOW_PRICE"].min())
        prev = float(df["CH_CLOSING_PRICE"].iloc[-2]) if len(df) > 1 else close
        chg = (close - prev) / prev * 100
        
        breakout = 224.60
        sl = round(breakout * 0.92, 2)
        t1 = 312.75
        watch = breakout * 0.90
        near = breakout * 0.95
        dist = (breakout - close) / close * 100
        
        print("COMSYN.NS — NSE DATA")
        print("=" * 55)
        print(f"  Latest close:  Rs.{close:.2f}  ({chg:+.2f}%)")
        print(f"  30-day high:   Rs.{high:.2f}")
        print(f"  30-day low:    Rs.{low:.2f}")
        print(f"  Breakout:      Rs.{breakout}")
        print(f"  Distance:      {dist:.1f}% below breakout")
        print()
        
        if close >= breakout:
            print(f"  STATUS: BREAKOUT — tradeable NOW!")
        elif close >= near:
            print(f"  STATUS: NEAR — set alert at Rs.{breakout}")
        elif close >= watch:
            print(f"  STATUS: WATCH — {(breakout-close)/close*100:.1f}% to go")
            print(f"  Needs Rs.{breakout - close:.2f} more to break out")
        else:
            print(f"  STATUS: FILTERED — too far from breakout")
        
        print()
        print(f"  IF BREAKOUT AT Rs.{breakout}:")
        print(f"    SL:  Rs.{sl}  (8% below, v3.1 cap)")
        print(f"    T1:  Rs.{t1}  (+{(t1-breakout)/breakout*100:.1f}%)")
        print(f"    R:R: 1:{(t1-breakout)/(breakout-sl):.1f}")
    else:
        print("No data returned")
except Exception as e:
    print(f"Error: {e}")
    # Try yfinance as fallback
    import yfinance as yf
    t = yf.Ticker("COMSYN.NS")
    h = t.history(period="1mo")
    if not h.empty:
        close = float(h["Close"].iloc[-1])
        print(f"\nyfinance fallback: COMSYN close = Rs.{close:.2f}")
    else:
        print("yfinance also returned no data")
