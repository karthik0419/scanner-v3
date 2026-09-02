"""Calculate trade risk for VEDL entry."""
entry = 263.40   # bought at market open
sl = 245.00
target = 330.00
qty = 80

capital_at_risk = (entry - sl) * qty
potential_profit = (target - entry) * qty
risk_pct = (entry - sl) / entry * 100
reward_pct = (target - entry) / entry * 100
rr = reward_pct / risk_pct

total_capital = entry * qty

print("=" * 55)
print(f"  VEDL TRADE — RISK CALCULATION")
print("=" * 55)
print(f"  Entry:    Rs.{entry:.2f}")
print(f"  Stop:     Rs.{sl:.2f}")
print(f"  Target:   Rs.{target:.2f}")
print(f"  Quantity: {qty} shares")
print(f"  Position size: Rs.{total_capital:,.2f}")
print(f"")
print(f"  Risk per share:   Rs.{entry - sl:.2f} ({risk_pct:.1f}%)")
print(f"  Reward per share: Rs.{target - entry:.2f} ({reward_pct:.1f}%)")
print(f"  R:R ratio:        1:{rr:.1f}")
print(f"")
print(f"  MAX LOSS if SL hit:    Rs.{capital_at_risk:,.2f}")
print(f"  PROFIT if target hit:  Rs.{potential_profit:,.2f}")
print(f"")
print(f"  Verdict: {'OK — risk within 8% protocol' if risk_pct <= 8 else 'WARNING: risk exceeds 8% protocol'}")
