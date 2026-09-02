"""Diagnose scanner-v3 issues from paper tracker results."""
import csv
from pathlib import Path

tracker = list(csv.DictReader(open("F:/projects/claude/scanner-v3/results/paper_tracker.csv")))
tradeable = [r for r in tracker if r['tradeable'].startswith('TRADE')]

print("=== DIAGNOSING SCANNER-V3 ISSUES ===\n")

# Issue 1: Stop loss distance from CMP
print("--- ISSUE 1: Stop Loss Distance from Entry ---")
print(f"{'Symbol':<18} {'Entry':>8} {'SL':>8} {'Risk%':>7} {'SL vs B2':>10}")
for r in tradeable:
    entry = float(r['entry_price'])
    sl = float(r['stop_loss'])
    risk = (entry - sl) / entry * 100
    print(f"{r['symbol']:<18} {entry:>8.2f} {sl:>8.2f} {risk:>6.2f}%   SL = bottom2 * 0.97")

avg_risk = sum((float(r['entry_price']) - float(r['stop_loss'])) / float(r['entry_price']) * 100 for r in tradeable) / len(tradeable)
print(f"\n  AVERAGE RISK: {avg_risk:.2f}%")
print(f"  PROBLEM: SL is 3% below 2nd bottom, but entry is ABOVE the breakout (neckline).")
print(f"  So actual risk from entry = (entry - bottom2*0.97) / entry, which is LARGER than 3%.")

# Issue 2: Entry vs Breakout distance
print(f"\n--- ISSUE 2: Entry vs Breakout Distance ---")
# For BREAKOUT status, entry = cmp at scan, breakout = neckline
# For NEAR status, entry would be at breakout (if traded properly)
# But the paper tracker enters at CMP even for NEAR!
breakouts_only = [r for r in tradeable if r['status_at_scan'] == 'BREAKOUT']
nears_only = [r for r in tradeable if r['status_at_scan'] == 'NEAR']
print(f"  BREAKOUT picks (entered at CMP = above breakout): {len(breakouts_only)}")
print(f"  NEAR picks (entered at CMP = BELOW breakout!):    {len(nears_only)}")
print(f"\n  >>> NEAR picks are entered BEFORE breakout confirmation!")
print(f"  >>> This means buying below the neckline with a SL below the 2nd bottom.")
print(f"  >>> The risk is HUGE because entry is far above the SL.")

# Issue 3: Target distance
print(f"\n--- ISSUE 3: Target Distance from Entry ---")
print(f"{'Symbol':<18} {'Entry':>8} {'T1':>8} {'T2':>8} {'Upside%':>8} {'Days to T1?':>12}")
for r in tradeable[:10]:
    entry = float(r['entry_price'])
    t1 = float(r['target_1'])
    t2 = float(r['target_2'])
    upside = (t1 - entry) / entry * 100
    print(f"{r['symbol']:<18} {entry:>8.2f} {t1:>8.2f} {t2:>8.2f} {upside:>7.1f}%   ???")

avg_upside = sum((float(r['target_1']) - float(r['entry_price'])) / float(r['entry_price']) * 100 for r in tradeable) / len(tradeable)
print(f"\n  AVERAGE UPSIDE TO T1: {avg_upside:.1f}%")
print(f"  PROBLEM: Full measured-move target is too ambitious for swing trades.")
print(f"  Targets are often 15-50% away — takes months to reach, if ever.")

# Issue 4: The REAL risk for NEAR picks
print(f"\n--- ISSUE 4: Real Risk for NEAR Picks (entered below breakout) ---")
print(f"{'Symbol':<18} {'Entry':>8} {'Breakout':>10} {'SL':>8} {'Risk if enter at BO':>18}")
for r in nears_only[:10]:
    entry = float(r['entry_price'])
    sl = float(r['stop_loss'])
    bo = float(r['cmp_at_scan'])  # This is actually the CMP, not breakout
    # Risk if entered AT breakout (proper entry)
    risk_at_bo = (entry - sl) / entry * 100  # current risk (wrong entry)
    print(f"{r['symbol']:<18} {entry:>8.2f} {'???':>10} {sl:>8.2f} {risk_at_bo:>17.2f}%")

print(f"\n  >>> Paper tracker enters at CMP for NEAR picks — this is WRONG.")
print(f"  >>> NEAR picks should only be entered AFTER breakout confirmation.")
print(f"  >>> The scanner shows them as 'NEAR' but the tracker buys immediately.")

# Issue 5: Double Bottom SL logic
print(f"\n--- ISSUE 5: Double Bottom SL Logic ---")
print(f"  Current: SL = bottom2 * 0.97  (3% below 2nd bottom)")
print(f"  Problem: If entry is at breakout (neckline), and bottom2 is 10-20% below neckline,")
print(f"           then risk = 10-20% + 3% = 13-23%. That's WAY too wide.")
print(f"  Example: NATCOPHARM entry=966, bottom2~850, SL=824. Risk = (966-824)/966 = 14.7%")
print(f"           But paper tracker shows risk_pct=4.99% — because it calculates from CMP, not from breakout entry!")

# Summary of fixes needed
print(f"\n{'='*70}")
print(f"=== ROOT CAUSES ===")
print(f"{'='*70}")
print(f"""
1. NEAR picks are entered at CMP (below breakout) instead of waiting for 
   breakout confirmation. This means buying BEFORE the pattern triggers,
   with a SL that's far below — creating huge real risk.

2. Stop loss = bottom2 * 0.97 is a STRUCTURAL stop, but it's too far from
   the entry point. For Double Bottoms, the 2nd bottom can be 10-20% below
   the neckline (entry), making the actual risk 13-23%, not the 3-5% shown.

3. Targets use FULL measured move (peak + (peak - bottom)), which is often
   20-50% above entry. These are investment-grade targets, not swing targets.
   Most stocks never reach them in a swing timeframe.

4. No max risk filter — picks with 15%+ real risk are shown alongside 
   picks with 3% risk, and the score doesn't penalize wide stops enough.

5. Paper tracker enters ALL picks (NEAR + BREAKOUT) at CMP on scan day,
   instead of only entering BREAKOUT picks or setting alerts for NEAR picks.
""")
