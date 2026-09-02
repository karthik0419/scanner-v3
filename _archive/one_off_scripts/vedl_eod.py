# VEDL live trade status from paper tracker data
entry = 263.40
sl = 245.00
target = 330.00
qty = 80
current = 264.50  # from paper tracker update

pnl = (current - entry) * qty
pnl_pct = (current - entry) / entry * 100
dist_sl = (current - sl) / current * 100
dist_tgt = (target - current) / current * 100

print("VEDL LIVE TRADE — EOD 29 Jul 2026")
print("Entry: Rs.", entry, "| SL: Rs.", sl, "| Target: Rs.", target, "| Qty:", qty)
print("Current: Rs.", current)
print("P&L: Rs.", round(pnl, 2), "(", round(pnl_pct, 2), "%)")
print("Distance to SL:", round(dist_sl, 1), "%  (Rs.", round(current - sl, 2), "away)")
print("Distance to Target:", round(dist_tgt, 1), "%  (Rs.", round(target - current, 2), "away)")
print("Max loss if SL hit: Rs.", round((entry - sl) * qty, 2))
print("Profit if target hit: Rs.", round((target - entry) * qty, 2))
