"""Final comparison: Previous v3 (1.5x ATR, bad) vs Fixed v3 (2.0x ATR + re-entry) vs v2."""
import pandas as pd

v3_new = pd.read_csv("F:/projects/claude/scanner-v3/results/backtest_v3.csv")
v2 = pd.read_csv("F:/projects/claude/scanner-v3/results/backtest_v2.csv")

# Previous v3 results (from the first backtest run before 2.0x fix)
prev_v3 = {
    "trades": 2389, "wins": 908, "losses": 1481,
    "win_rate": 38.0, "avg_win": 9.09, "avg_loss": -3.44,
    "expectancy": 1.32, "pf": 1.62, "dd": -73.9, "avg_risk": 4.94
}

def stats(df):
    total = len(df)
    wins = (df["result"] == "WIN").sum()
    losses = (df["result"] == "LOSS").sum()
    avg_win = df.loc[df["result"] == "WIN", "pnl_pct"].mean()
    avg_loss = df.loc[df["result"] == "LOSS", "pnl_pct"].mean()
    wr = wins / total * 100
    exp = (wins/total * avg_win) + (losses/total * avg_loss)
    gp = df.loc[df["pnl_pct"] > 0, "pnl_pct"].sum()
    gl = abs(df.loc[df["pnl_pct"] < 0, "pnl_pct"].sum())
    pf = gp / gl
    equity = (1 + df["pnl_pct"] / 100).cumprod()
    dd = ((equity - equity.cummax()) / equity.cummax() * 100).min()
    avg_risk = ((df["entry_price"] - df["stop_loss"]) / df["entry_price"] * 100).mean()
    return {"trades": total, "wins": wins, "losses": losses, "win_rate": round(wr,1),
            "avg_win": round(avg_win,2), "avg_loss": round(avg_loss,2),
            "expectancy": round(exp,2), "pf": round(pf,2), "dd": round(dd,1),
            "avg_risk": round(avg_risk,2)}

s_new = stats(v3_new)
s_v2 = stats(v2)

print("=" * 85)
print("  FINAL BACKTEST: Nifty 200 (178 stocks, 2 years, min_score=40)")
print("=" * 85)
print(f"\n  {'Metric':<20} {'Prev v3 (1.5x)':>16} {'Fixed v3 (2.0x)':>17} {'v2 (original)':>15} {'v3 vs v2':>10}")
print(f"  {'-'*80}")
for key, label in [("trades","Trades"), ("wins","Wins"), ("losses","Losses"),
                   ("win_rate","Win rate %"), ("avg_win","Avg win %"), ("avg_loss","Avg loss %"),
                   ("expectancy","Expectancy %"), ("pf","Profit factor"), ("dd","Max DD %"),
                   ("avg_risk","Avg risk %")]:
    pv = prev_v3[key]
    nv = s_new[key]
    v2v = s_v2[key]
    delta = nv - v2v
    if key in ("win_rate", "avg_win", "avg_loss", "expectancy", "dd", "avg_risk"):
        print(f"  {label:<20} {pv:>15.1f} {nv:>16.1f} {v2v:>14.1f} {delta:>+9.1f}")
    elif key == "pf":
        print(f"  {label:<20} {pv:>16.2f} {nv:>17.2f} {v2v:>15.2f} {delta:>+9.2f}")
    else:
        print(f"  {label:<20} {pv:>16} {nv:>17} {v2v:>15} {delta:>+9}")

# Re-entry performance
re_entries = v3_new[v3_new["pattern"] == "Re-entry"]
if len(re_entries) > 0:
    re_wins = (re_entries["result"] == "WIN").sum()
    re_wr = re_wins / len(re_entries) * 100
    re_avg = re_entries["pnl_pct"].mean()
    print(f"\n  RE-ENTRY TRADES: {len(re_entries)} | WR: {re_wr:.1f}% | Avg P&L: +{re_avg:.2f}%")

# Exit reasons
print(f"\n  EXIT REASONS (v3 2.0x):")
for reason in sorted(v3_new["exit_reason"].unique()):
    sub = v3_new[v3_new["exit_reason"] == reason]
    print(f"    {reason:<15} {len(sub):>5} trades | avg {sub['pnl_pct'].mean():>+6.2f}%")

# Pattern breakdown
print(f"\n  TOP PATTERNS (v3 2.0x, by trade count):")
pat_stats = v3_new.groupby("pattern").agg(
    trades=("pnl_pct","count"), 
    wr=("result", lambda x: f"{(x=='WIN').mean()*100:.1f}%"),
    avg=("pnl_pct", lambda x: f"{x.mean():+.2f}%")
).sort_values("trades", ascending=False)
for pat, row in pat_stats.head(10).iterrows():
    print(f"    {pat:<25} {row['trades']:>5} trades | WR: {row['wr']:>6} | Avg: {row['avg']:>8}")

print(f"\n  VERDICT:")
print(f"    v3 (2.0x) beats v2 on: expectancy (+{s_new['expectancy']-s_v2['expectancy']:.2f}%), "
      f"PF ({s_new['pf']} vs {s_v2['pf']}), avg loss ({s_new['avg_loss']} vs {s_v2['avg_loss']})")
print(f"    v3 (2.0x) beats prev v3 (1.5x) on: expectancy (+{s_new['expectancy']-prev_v3['expectancy']:.2f}%), "
      f"PF ({s_new['pf']} vs {prev_v3['pf']}), DD ({s_new['dd']} vs {prev_v3['dd']}), avg loss ({s_new['avg_loss']} vs {prev_v3['avg_loss']})")
