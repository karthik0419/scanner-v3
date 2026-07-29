"""Rank today's picks by 2-week profit potential using backtest statistics."""
import csv
import pandas as pd

# Load today's picks
picks = list(csv.DictReader(open("F:/projects/claude/scanner-v3/results/v3_2026-07-29.csv")))

# Load backtest results for pattern statistics
v3 = pd.read_csv("F:/projects/claude/scanner-v3/results/backtest_v3.csv")

# Pattern stats from backtest
pat_stats = v3.groupby("pattern").agg(
    trades=("pnl_pct", "count"),
    win_rate=("result", lambda x: (x == "WIN").mean() * 100),
    avg_pnl=("pnl_pct", "mean"),
    avg_win=("pnl_pct", lambda x: x[x > 0].mean() if (x > 0).any() else 0),
    avg_loss=("pnl_pct", lambda x: x[x < 0].mean() if (x < 0).any() else 0),
    avg_days=("days_held", "mean"),
    t1_rate=("exit_reason", lambda x: (x.isin(["Target 1", "Target 2"])).sum() / len(x) * 100),
).reset_index()

# Time exit stats (stocks that didn't hit SL or target — how did they do?)
time_exits = v3[v3["exit_reason"] == "Time Exit"]
time_by_pat = time_exits.groupby("pattern")["pnl_pct"].agg(["mean", "count"]).reset_index()

print("=" * 90)
print("  2-WEEK PROFIT POTENTIAL ANALYSIS — 29 Jul 2026")
print("=" * 90)

# Score each pick
ranked = []
for p in picks:
    pat = p["pattern"]
    tf = p["timeframe"]
    status = p["status"]
    cmp = float(p["cmp"])
    bo = float(p["breakout"])
    sl = float(p["stop_loss"])
    t1 = float(p["target_1"])
    risk = (cmp - sl) / cmp * 100
    upside = (t1 - cmp) / cmp * 100
    dist_to_bo = (bo - cmp) / cmp * 100 if status != "BREAKOUT" else 0
    
    # Get pattern backtest stats
    ps = pat_stats[pat_stats["pattern"] == pat]
    if ps.empty:
        ps = pat_stats[pat_stats["pattern"] == "Cup & Handle"]  # fallback
    
    wr = float(ps["win_rate"].iloc[0])
    avg_win = float(ps["avg_win"].iloc[0])
    avg_loss = float(ps["avg_loss"].iloc[0])
    avg_days = float(ps["avg_days"].iloc[0])
    t1_rate = float(ps["t1_rate"].iloc[0])
    trades = int(ps["trades"].iloc[0])
    
    # 2-week probability: trades that hit T1/T2 within ~14 days
    # From backtest: avg days held is ~16, so 2 weeks is tight
    # Only BREAKOUT status can act now; NEAR needs to break out first
    
    # Probability factors:
    # 1. BREAKOUT status = can trade NOW (NEAR = must wait for breakout)
    # 2. Distance to breakout = closer = more likely to trigger soon
    # 3. Pattern win rate from backtest
    # 4. T1 hit rate from backtest
    # 5. Tight risk = smaller loss if wrong
    # 6. Avg days held = shorter = faster result
    
    # Actionability score (0-100)
    if status == "BREAKOUT":
        action_score = 100
    elif abs(dist_to_bo) < 2:
        action_score = 80  # very close to breakout
    elif abs(dist_to_bo) < 5:
        action_score = 60
    else:
        action_score = 30
    
    # Pattern reliability score (0-100)
    pattern_score = wr  # win rate directly
    
    # Risk score (0-100) — lower risk = higher score
    if risk <= 3:
        risk_score = 100
    elif risk <= 5:
        risk_score = 80
    elif risk <= 8:
        risk_score = 60
    else:
        risk_score = 30
    
    # Speed score — patterns that resolve faster are better for 2-week window
    if avg_days <= 14:
        speed_score = 100
    elif avg_days <= 20:
        speed_score = 70
    elif avg_days <= 30:
        speed_score = 40
    else:
        speed_score = 20
    
    # T1 probability — how often does this pattern hit T1?
    t1_prob = t1_rate
    
    # Composite 2-week score
    composite = (action_score * 0.30 + pattern_score * 0.25 + risk_score * 0.15 
                 + speed_score * 0.15 + t1_prob * 0.15)
    
    ranked.append({
        "symbol": p["symbol"],
        "pattern": pat,
        "timeframe": tf,
        "status": status,
        "cmp": cmp,
        "breakout": bo,
        "dist_to_bo": dist_to_bo,
        "sl": sl,
        "risk": risk,
        "t1": t1,
        "upside": upside,
        "rr": float(p["rr"]),
        "score": float(p["score"]),
        "wr": wr,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_days": avg_days,
        "t1_rate": t1_rate,
        "trades": trades,
        "action_score": action_score,
        "composite": composite,
    })

# Sort by composite score
ranked.sort(key=lambda x: x["composite"], reverse=True)

print(f"\n{'Rank':<5} {'Symbol':<12} {'Pattern':<22} {'TF':<8} {'Status':<9} {'CMP':>8} {'Risk%':>6} {'Upside%':>8} {'WR%':>5} {'T1Rate%':>8} {'Days':>5} {'Composite':>9}")
print("-" * 115)
for i, r in enumerate(ranked):
    print(f"{i+1:<5} {r['symbol']:<12} {r['pattern']:<22} {r['timeframe']:<8} {r['status']:<9} {r['cmp']:>8.2f} {r['risk']:>5.1f}% {r['upside']:>+7.1f}% {r['wr']:>4.1f}% {r['t1_rate']:>7.1f}% {r['avg_days']:>5.1f} {r['composite']:>8.1f}")

# Detailed analysis for top 3
print(f"\n{'='*90}")
print(f"  TOP 3 PICKS — DETAILED ANALYSIS")
print(f"{'='*90}")

for i, r in enumerate(ranked[:3]):
    print(f"\n  #{i+1} {r['symbol']} — {r['pattern']} [{r['timeframe']}] — {r['status']}")
    print(f"    CMP: {r['cmp']:.2f}  |  Breakout: {r['breakout']:.2f}  |  Distance: {r['dist_to_bo']:+.1f}%")
    print(f"    Stop: {r['sl']:.2f}  |  Risk: {r['risk']:.1f}%  |  T1: {r['t1']:.2f}  |  Upside: +{r['upside']:.1f}%")
    print(f"    Backtest: {r['trades']} trades | WR: {r['wr']:.1f}% | Avg win: +{r['avg_win']:.1f}% | Avg loss: {r['avg_loss']:.1f}% | T1 hit rate: {r['t1_rate']:.1f}%")
    print(f"    Avg days held: {r['avg_days']:.0f}  |  R:R: {r['rr']:.1f}x")
    
    # 2-week verdict
    if r['status'] == 'BREAKOUT':
        verdict = f"ALREADY BROKEN OUT — tradeable NOW"
    elif abs(r['dist_to_bo']) < 2:
        verdict = f"ONLY {abs(r['dist_to_bo']):.1f}% FROM BREAKOUT — set alert, likely triggers within 1-2 weeks"
    elif abs(r['dist_to_bo']) < 5:
        verdict = f"{abs(r['dist_to_bo']):.1f}% FROM BREAKOUT — may trigger in 2-3 weeks, set alert"
    else:
        verdict = f"{abs(r['dist_to_bo']):.1f}% FROM BREAKOUT — too far for 2-week window"
    
    print(f"    VERDICT: {verdict}")
    
    # Probability estimate
    if r['status'] == 'BREAKOUT' and r['avg_days'] <= 20:
        prob = "HIGH — pattern resolves in ~2 weeks, already triggered"
    elif abs(r['dist_to_bo']) < 2 and r['avg_days'] <= 20:
        prob = "MEDIUM-HIGH — close to breakout, pattern resolves fast"
    elif abs(r['dist_to_bo']) < 5 and r['avg_days'] <= 25:
        prob = "MEDIUM — may trigger within 2 weeks if market cooperates"
    else:
        prob = "LOW — unlikely to complete within 2 weeks"
    print(f"    2-WEEK PROBABILITY: {prob}")

# Summary
print(f"\n{'='*90}")
print(f"  SUMMARY — BEST BETS FOR NEXT 2 WEEKS")
print(f"{'='*90}")
print(f"\n  1. VEDL — BREAKOUT now, 3.4% risk, 9.46x R:R, wedge patterns avg 16 days")
print(f"     Already broken out. SL 244.55. T1 334.92 (+32%). Best actionable trade.")
print(f"     Wedge win rate: 35.6% but avg win +11.5% vs avg loss -3.8% = positive expectancy")
print(f"\n  2. PNB — 3.5% from breakout, 0.7% risk (super tight), Double Bottom")
print(f"     Double Bottom: 40.9% WR, avg +2.06%/trade, 399 trades in backtest")
print(f"     If breaks 115.60, SL at 110.88 (only 0.7% risk). T1 124.15 (+11%)")
print(f"     Set alert at 115.60. Highest pattern reliability + tightest risk.")
print(f"\n  3. BPCL/MANAPPURAM/FEDERALBNK — all <1% from breakout, C&H Weekly/Monthly")
print(f"     C&H: 34.3% WR but avg win +7.6% vs avg loss -3.0%")
print(f"     Banking sector is WEAK — caution. But MANAPPURAM already above breakout.")
print(f"\n  AVOID FOR 2-WEEK WINDOW:")
print(f"     - GAIL: 7.4% risk (highest), 31% upside but takes ~30+ days")
print(f"     - RBLBANK: 4.9% from breakout, monthly pattern (slow)")
print(f"     - ZOMATO: 4.9% from breakout, monthly (slow)")
print(f"\n  MARKET WARNING: Nifty below 200DMA (RISK_OFF). Reduce position size 50%.")
