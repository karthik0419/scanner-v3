import yfinance as yf

# COMSYN — check latest price
t = yf.Ticker("COMSYN.NS")
h = t.history(period="1mo")
if h.empty:
    print("COMSYN: no data from yfinance")
else:
    close = float(h["Close"].iloc[-1])
    high = float(h["High"].max())
    low = float(h["Low"].min())
    prev = float(h["Close"].iloc[-2]) if len(h) > 1 else close
    chg = (close - prev) / prev * 100
    
    breakout = 224.60
    sl_capped = round(breakout * 0.92, 2)  # 8% below breakout
    t1 = 312.75
    t2 = 371.52
    watch_zone = breakout * 0.90  # 10% below
    near_zone = breakout * 0.95   # 5% below
    
    dist = (breakout - close) / close * 100
    
    print("COMSYN.NS — LATEST PRICE")
    print("=" * 55)
    print(f"  Current close:  Rs.{close:.2f}  ({chg:+.2f}% today)")
    print(f"  1-month high:   Rs.{high:.2f}")
    print(f"  1-month low:    Rs.{low:.2f}")
    print(f"  Breakout level: Rs.{breakout:.2f}")
    print(f"  Distance:       {dist:.1f}% below breakout")
    print()
    
    if close >= breakout:
        status = "BREAKOUT — tradeable now!"
    elif close >= near_zone:
        status = "NEAR — set alert at Rs.%.2f" % breakout
    elif close >= watch_zone:
        status = "WATCH — approaching, %.1f%% to go" % ((breakout - close) / close * 100)
    else:
        status = "FILTERED — too far from breakout"
    
    print(f"  STATUS: {status}")
    print()
    
    if close >= watch_zone:
        print(f"  IF BREAKOUT TRIGGERS AT Rs.{breakout}:")
        print(f"    SL (v3.1 cap):  Rs.{sl_capped}  (8% below)")
        print(f"    T1:             Rs.{t1:.2f}  (+{(t1-breakout)/breakout*100:.1f}%)")
        print(f"    T2:             Rs.{t2:.2f}  (+{(t2-breakout)/breakout*100:.1f}%)")
        print(f"    R:R =           1:{(t1-breakout)/(breakout-sl_capped):.1f}")
        print()
        print(f"  Watch zone:  Rs.{watch_zone:.2f} - Rs.{near_zone:.2f}")
        print(f"  Near zone:   Rs.{near_zone:.2f} - Rs.{breakout:.2f}")
        print(f"  Breakout:    above Rs.{breakout:.2f}")
