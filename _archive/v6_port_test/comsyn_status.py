cmp_today = 207.0
breakout = 224.60
sl_old = 148.47
sl_capped = round(breakout * 0.92, 2)  # 8% below breakout (v3.1 protocol)
t1 = 312.75
t2 = 371.52

dist_to_bo = (breakout - cmp_today) / cmp_today * 100
watch_threshold = breakout * 0.90  # 10% below breakout
near_threshold = breakout * 0.95   # 5% below breakout

print("COMSYN STATUS AFTER TODAY'S JUMP")
print("=" * 55)
print(f"  Today's close:  Rs.{cmp_today:.2f}")
print(f"  Breakout level: Rs.{breakout:.2f}")
print(f"  Distance:       {dist_to_bo:.1f}% below breakout")
print(f"  Volume:         confirmed (was True in scan)")
print()
print(f"  V3.1 THRESHOLDS:")
print(f"    WATCH zone:  Rs.{watch_threshold:.2f} - Rs.{near_threshold:.2f}")
print(f"    NEAR zone:   Rs.{near_threshold:.2f} - Rs.{breakout:.2f}")
print(f"    BREAKOUT:    above Rs.{breakout:.2f}")
print()
if cmp_today >= breakout:
    status = "BREAKOUT"
elif cmp_today >= near_threshold:
    status = "NEAR"
elif cmp_today >= watch_threshold:
    status = "WATCH"
else:
    status = "FILTERED OUT"
print(f"  CURRENT STATUS: {status}")
print()
if status == "WATCH":
    print(f"  COMSYN is now in the WATCH zone!")
    print(f"  Needs to reach Rs.{near_threshold:.2f} for NEAR status")
    print(f"  That is only {((near_threshold - cmp_today) / cmp_today * 100):.1f}% away")
    print(f"  At today's momentum, could reach NEAR in 1-2 sessions")
elif status == "NEAR":
    print(f"  COMSYN is now NEAR breakout — set price alert!")
print()
print(f"  IF IT BREAKS OUT AT Rs.{breakout}:")
print(f"    SL (v3.1 capped): Rs.{sl_capped} (8% below breakout)")
print(f"    Risk from breakout: 8.0%")
print(f"    T1: Rs.{t1:.2f} (+{(t1-breakout)/breakout*100:.1f}%)")
print(f"    T2: Rs.{t2:.2f} (+{(t2-breakout)/breakout*100:.1f}%)")
print(f"    R:R = 1:{(t1-breakout)/(breakout-sl_capped):.1f}")
print()
print(f"  OLD SL was Rs.{sl_old} (14.9% risk) — v3.1 caps it at Rs.{sl_capped}")
print(f"  The old scan had this at 28.7% from breakout — now only {dist_to_bo:.1f}%!")
