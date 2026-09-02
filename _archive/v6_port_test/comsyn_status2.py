close = 217.58
breakout = 224.60
sl = round(breakout * 0.92, 2)
t1 = 312.75
t2 = 371.52
watch = breakout * 0.90
near = breakout * 0.95
dist = (breakout - close) / close * 100

print("COMSYN.NS — CURRENT STATUS")
print("=" * 55)
print(f"  Latest close:  Rs.{close}")
print(f"  Breakout:      Rs.{breakout}")
print(f"  Distance:      {dist:.1f}% below breakout")
print(f"  Needs:         Rs.{breakout - close:.2f} more to break out")
print()

if close >= breakout:
    print(f"  STATUS: BREAKOUT")
elif close >= near:
    print(f"  STATUS: NEAR (within 5% of breakout)")
elif close >= watch:
    print(f"  STATUS: WATCH (within 10% of breakout)")
else:
    print(f"  STATUS: FILTERED (too far)")

print()
print(f"  ZONES:")
print(f"    WATCH:  Rs.{watch:.2f} - Rs.{near:.2f}")
print(f"    NEAR:   Rs.{near:.2f} - Rs.{breakout:.2f}")
print(f"    BREAK:  above Rs.{breakout:.2f}")
print()
print(f"  COMSYN at Rs.{close} is in the WATCH zone!")
print(f"  Only {dist:.1f}% from breakout")
print(f"  Up from Rs.174.48 on July 27 = +{((close-174.48)/174.48*100):.1f}% in 2 days")
print()
print(f"  IF IT BREAKS OUT AT Rs.{breakout}:")
print(f"    SL (v3.1):  Rs.{sl}  (8% below)")
print(f"    T1:         Rs.{t1}  (+{(t1-breakout)/breakout*100:.1f}%)")
print(f"    T2:         Rs.{t2}  (+{(t2-breakout)/breakout*100:.1f}%)")
print(f"    R:R:        1:{(t1-breakout)/(breakout-sl):.1f}")
print()
print(f"  OLD SL was Rs.148.47 (14.9% risk) — v3.1 caps it at Rs.{sl} (8%)")
print(f"  The SL is right around current price ({close}) — manageable risk")
