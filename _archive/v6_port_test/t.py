entry = 263.40
sl = 245.00
tgt = 330.00
qty = 80

risk = (entry - sl) * qty
profit = (tgt - entry) * qty
position = entry * qty
risk_pct = round((entry - sl) / entry * 100, 1)
reward_pct = round((tgt - entry) / entry * 100, 1)
rr = round((tgt - entry) / (entry - sl), 1)

print("VEDL TRADE")
print("Entry:", entry)
print("SL:", sl)
print("Target:", tgt)
print("Qty:", qty)
print("Position size: Rs.", position)
print("Max loss if SL hit: Rs.", risk)
print("Profit if target hit: Rs.", profit)
print("Risk %:", risk_pct)
print("Reward %:", reward_pct)
print("R:R = 1:", rr)
