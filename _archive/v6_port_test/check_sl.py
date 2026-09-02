"""Check which paper tracker picks hit stop loss or target."""
import csv
import yfinance as yf
from datetime import datetime
from pathlib import Path

tracker_path = Path("F:/projects/claude/scanner-v3/results/paper_tracker.csv")
rows = list(csv.DictReader(open(tracker_path)))

print(f"=== Paper Tracker Status Check ===")
print(f"Scan date: 2026-07-17 | Today: {datetime.now().strftime('%Y-%m-%d')}")
print(f"Total tracked picks: {len(rows)}\n")

# Skip non-tradeable picks
tradeable = [r for r in rows if r['tradeable'].startswith('TRADE')]
skipped = [r for r in rows if r['tradeable'].startswith('SKIP')]
print(f"Tradeable: {len(tradeable)} | Skipped: {len(skipped)}\n")

results = []
hit_sl = []
hit_t1 = []
hit_t2 = []
errors = []

for r in tradeable:
    sym = r['symbol']
    entry = float(r['entry_price'])
    sl = float(r['stop_loss'])
    t1 = float(r['target_1'])
    t2 = float(r['target_2'])
    
    try:
        tk = yf.Ticker(sym)
        hist = tk.history(period="1mo", interval="1d")
        if hist.empty:
            errors.append((sym, "no data"))
            continue
        
        current = float(hist['Close'].iloc[-1])
        low_since = float(hist['Low'].min())
        high_since = float(hist['High'].max())
        
        pnl_pct = ((current - entry) / entry) * 100
        days_held = (datetime.now() - datetime.strptime(r['scan_date'], '%Y-%m-%d')).days
        
        status = "OPEN"
        exit_reason = ""
        
        if low_since <= sl:
            status = "STOPPED_OUT"
            exit_reason = f"SL hit (low: {low_since:.2f} <= SL: {sl:.2f})"
            hit_sl.append((sym, r['pattern'], entry, sl, low_since, pnl_pct))
        elif high_since >= t2:
            status = "T2_HIT"
            exit_reason = f"Target 2 hit (high: {high_since:.2f} >= T2: {t2:.2f})"
            hit_t2.append((sym, entry, t2, pnl_pct))
        elif high_since >= t1:
            status = "T1_HIT"
            exit_reason = f"Target 1 hit (high: {high_since:.2f} >= T1: {t1:.2f})"
            hit_t1.append((sym, entry, t1, pnl_pct))
        
        results.append({
            'symbol': sym,
            'pattern': r['pattern'],
            'entry': entry,
            'sl': sl,
            't1': t1,
            'current': current,
            'pnl_pct': round(pnl_pct, 2),
            'status': status,
            'days': days_held,
            'exit_reason': exit_reason,
            'low_since': low_since,
            'high_since': high_since,
        })
    except Exception as e:
        errors.append((sym, str(e)))

# Print results
print(f"{'Symbol':<18} {'Pattern':<22} {'Entry':>8} {'SL':>8} {'CMP':>8} {'PnL%':>7} {'Status':<12} {'Days':>4}")
print("-" * 95)
for r in sorted(results, key=lambda x: x['pnl_pct']):
    print(f"{r['symbol']:<18} {r['pattern']:<22} {r['entry']:>8.2f} {r['sl']:>8.2f} {r['current']:>8.2f} {r['pnl_pct']:>+7.2f}% {r['status']:<12} {r['days']:>4}")

# Summary
print(f"\n=== SUMMARY ===")
print(f"  Total tradeable: {len(tradeable)}")
print(f"  Stopped out (SL hit):  {len(hit_sl)}")
print(f"  Target 1 hit:          {len(hit_t1)}")
print(f"  Target 2 hit:          {len(hit_t2)}")
print(f"  Still open:            {len([r for r in results if r['status'] == 'OPEN'])}")
print(f"  Errors:                {len(errors)}")

if hit_sl:
    print(f"\n--- STOPPED OUT (SL Hit) ---")
    for sym, pat, entry, sl, low, pnl in hit_sl:
        print(f"  {sym:<18} {pat:<22} Entry:{entry:>8.2f} SL:{sl:>8.2f} Low:{low:>8.2f} PnL:{pnl:>+7.2f}%")

if hit_t1:
    print(f"\n--- TARGET 1 HIT ---")
    for sym, entry, t1, pnl in hit_t1:
        print(f"  {sym:<18} Entry:{entry:>8.2f} T1:{t1:>8.2f} PnL:{pnl:>+7.2f}%")

if hit_t2:
    print(f"\n--- TARGET 2 HIT ---")
    for sym, entry, t2, pnl in hit_t2:
        print(f"  {sym:<18} Entry:{entry:>8.2f} T2:{t2:>8.2f} PnL:{pnl:>+7.2f}%")

# Win/loss stats
closed = [r for r in results if r['status'] != 'OPEN']
if closed:
    wins = [r for r in closed if r['pnl_pct'] > 0]
    losses = [r for r in closed if r['pnl_pct'] <= 0]
    print(f"\n--- CLOSED TRADE STATS ---")
    print(f"  Wins:   {len(wins)}  ({len(wins)/len(closed)*100:.0f}%)")
    print(f"  Losses: {len(losses)} ({len(losses)/len(closed)*100:.0f}%)")
    if wins:
        print(f"  Avg win:  +{sum(w['pnl_pct'] for w in wins)/len(wins):.2f}%")
    if losses:
        print(f"  Avg loss: {sum(l['pnl_pct'] for l in losses)/len(losses):.2f}%")

# Open positions stats
opens = [r for r in results if r['status'] == 'OPEN']
if opens:
    print(f"\n--- OPEN POSITIONS ---")
    avg_pnl = sum(r['pnl_pct'] for r in opens) / len(opens)
    green = [r for r in opens if r['pnl_pct'] > 0]
    red = [r for r in opens if r['pnl_pct'] <= 0]
    print(f"  Green: {len(green)} | Red: {len(red)} | Avg PnL: {avg_pnl:+.2f}%")
    print(f"  Best:  {max(opens, key=lambda x: x['pnl_pct'])['symbol']} ({max(r['pnl_pct'] for r in opens):+.2f}%)")
    print(f"  Worst: {min(opens, key=lambda x: x['pnl_pct'])['symbol']} ({min(r['pnl_pct'] for r in opens):+.2f}%)")

if errors:
    print(f"\n--- ERRORS ---")
    for sym, err in errors:
        print(f"  {sym}: {err}")
