"""Check distance from CMP to breakout for latest scan — the real problem."""
import csv

rows = list(csv.DictReader(open("F:/projects/claude/scanner-v3/results/v3_2026-07-27.csv")))

print("=== DISTANCE FROM CMP TO BREAKOUT (Latest Scan) ===\n")
print(f"{'Symbol':<18} {'CMP':>8} {'Breakout':>10} {'Away%':>7} {'SL':>8} {'Risk%':>7} {'T1':>8} {'Upside%':>8} {'Real_RR':>8}")
print("-" * 95)

problems = []
for r in rows:
    cmp = float(r['cmp'])
    bo = float(r['breakout'])
    sl = float(r['stop_loss'])
    t1 = float(r['target_1'])
    away = (bo - cmp) / cmp * 100
    risk = (cmp - sl) / cmp * 100
    upside = (t1 - cmp) / cmp * 100
    # Real RR if entered at breakout
    real_risk_at_bo = (bo - sl) / bo * 100
    real_rr = (t1 - bo) / (bo - sl) if (bo - sl) > 0 else 0
    print(f"{r['symbol']:<18} {cmp:>8.2f} {bo:>10.2f} {away:>6.1f}% {sl:>8.2f} {risk:>6.1f}% {t1:>8.2f} {upside:>7.1f}% {real_rr:>8.2f}")
    
    if away > 5:
        problems.append((r['symbol'], 'far_from_breakout', away))
    if risk > 8:
        problems.append((r['symbol'], 'wide_stop', risk))

print(f"\n--- PROBLEMS ---")
far = [p for p in problems if p[1] == 'far_from_breakout']
wide = [p for p in problems if p[1] == 'wide_stop']
print(f"  >5% from breakout: {len(far)}/{len(rows)}")
for s, _, v in far:
    print(f"    {s}: {v:.1f}% away")
print(f"  >8% stop loss:    {len(wide)}/{len(rows)}")
for s, _, v in wide:
    print(f"    {s}: {v:.1f}% risk")
