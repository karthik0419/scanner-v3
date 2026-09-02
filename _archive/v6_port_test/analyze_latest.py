"""Analyze latest scanner-v3 results."""
import csv
from collections import Counter
from pathlib import Path

csv_path = Path("F:/projects/claude/scanner-v3/results/v3_2026-07-27.csv")
rows = list(csv.DictReader(open(csv_path)))

print(f"=== Scanner-v3 Results: {csv_path.name} ===")
print(f"Total picks: {len(rows)}\n")

# Status breakdown
status = Counter(r['status'] for r in rows)
print("--- Status Breakdown ---")
for s, c in status.most_common():
    print(f"  {s:12s}: {c}")

# Pattern breakdown
patterns = Counter(r['pattern'] for r in rows)
print("\n--- Pattern Breakdown ---")
for p, c in patterns.most_common():
    print(f"  {p:20s}: {c}")

# Timeframe breakdown
tfs = Counter(r['timeframe'] for r in rows)
print("\n--- Timeframe Breakdown ---")
for t, c in tfs.most_common():
    print(f"  {t:10s}: {c}")

# Sector breakdown
sectors = Counter(r['sector'] for r in rows)
print("\n--- Sector Breakdown ---")
for s, c in sectors.most_common():
    print(f"  {s:25s}: {c}")

# Sector signal
sigs = Counter(r['sector_signal'] for r in rows)
print("\n--- Sector Signal ---")
for s, c in sigs.most_common():
    print(f"  {s:12s}: {c}")

# Volume confirmation
vol = sum(1 for r in rows if r['volume'] == 'True')
print(f"\n--- Volume Confirmation ---")
print(f"  Volume confirmed: {vol}/{len(rows)} ({vol/len(rows)*100:.0f}%)")

# Risk/Reward stats
rrs = [float(r['rr']) for r in rows if r['rr']]
upsides = [float(r['upside_%']) for r in rows if r['upside_%']]
risks = [float(r['risk_%']) for r in rows if r['risk_%']]
scores = [float(r['score']) for r in rows if r['score']]

print(f"\n--- Risk/Reward Stats ---")
print(f"  Avg upside:    {sum(upsides)/len(upsides):.1f}%")
print(f"  Avg risk:      {sum(risks)/len(risks):.1f}%")
print(f"  Avg R:R:       {sum(rrs)/len(rrs):.2f}")
print(f"  Avg score:     {sum(scores)/len(scores):.1f}")
print(f"  Best R:R:      {max(rrs):.2f} ({rows[[i for i,r in enumerate(rows) if float(r['rr'])==max(rrs)][0]]['symbol']})")
print(f"  Worst R:R:     {min(rrs):.2f} ({rows[[i for i,r in enumerate(rows) if float(r['rr'])==min(rrs)][0]]['symbol']})")

# Top 5 by score
print(f"\n--- Top 5 by Score ---")
top5 = sorted(rows, key=lambda r: float(r['score']), reverse=True)[:5]
for r in top5:
    print(f"  {r['symbol']:18s} {r['pattern']:20s} {r['timeframe']:8s} {r['status']:8s} "
          f"CMP:{r['cmp']:>8s} R:R:{r['rr']:>5s} Score:{r['score']:>5s} Sector:{r['sector']}")

# BREAKOUT picks (actionable now)
breakouts = [r for r in rows if r['status'] == 'BREAKOUT']
print(f"\n--- BREAKOUT Picks (Actionable NOW) ---")
for r in breakouts:
    print(f"  {r['symbol']:18s} {r['pattern']:20s} {r['timeframe']:8s} "
          f"CMP:{r['cmp']:>8s} SL:{r['stop_loss']:>8s} T1:{r['target_1']:>8s} "
          f"R:R:{r['rr']:>5s} Vol:{r['volume']}")

# NEAR picks (watch for breakout)
nears = [r for r in rows if r['status'] == 'NEAR']
print(f"\n--- NEAR Picks (Watch for breakout) ---")
for r in nears[:10]:
    print(f"  {r['symbol']:18s} {r['pattern']:20s} {r['timeframe']:8s} "
          f"CMP:{r['cmp']:>8s} BO:{r['breakout']:>8s} "
          f"({(float(r['breakout'])-float(r['cmp']))/float(r['cmp'])*100:.1f}% away) "
          f"R:R:{r['rr']:>5s}")

# Price range distribution
prices = [float(r['cmp']) for r in rows]
print(f"\n--- Price Range ---")
print(f"  Min:  Rs.{min(prices):.2f}")
print(f"  Max:  Rs.{max(prices):.2f}")
print(f"  Avg:  Rs.{sum(prices)/len(prices):.2f}")
under_400 = sum(1 for p in prices if p <= 400)
under_200 = sum(1 for p in prices if p <= 200)
print(f"  Under Rs.400: {under_400}/{len(rows)}")
print(f"  Under Rs.200: {under_200}/{len(rows)}")

# Monthly picks (higher conviction, longer hold)
monthly = [r for r in rows if r['timeframe'] == 'Monthly']
print(f"\n--- Monthly Picks (High Conviction) ---")
for r in monthly:
    print(f"  {r['symbol']:18s} {r['pattern']:20s} {r['status']:8s} "
          f"Upside:{r['upside_%']:>6s}% R:R:{r['rr']:>5s} Score:{r['score']}")

# Neckline analysis for C&H
ch_picks = [r for r in rows if 'Cup & Handle' in r['pattern']]
necklines = Counter(r['neckline'] for r in ch_picks)
print(f"\n--- C&H Neckline Analysis ({len(ch_picks)} picks) ---")
for n, c in necklines.most_common():
    print(f"  {n:15s}: {c}")
