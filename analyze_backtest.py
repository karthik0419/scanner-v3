"""Analyze backtest results — v3 (fixed) vs v2 (original)."""
import pandas as pd

v3 = pd.read_csv("F:/projects/claude/scanner-v3/results/backtest_v3.csv")
v2 = pd.read_csv("F:/projects/claude/scanner-v3/results/backtest_v2.csv")

print("=" * 70)
print("  BACKTEST ANALYSIS: v3 (FIXED) vs v2 (ORIGINAL)")
print("  178 stocks | 2 years | min_score=40")
print("=" * 70)

# Overall comparison
for label, df in [("v3 (FIXED)", v3), ("v2 (ORIGINAL)", v2)]:
    total = len(df)
    wins = (df["result"] == "WIN").sum()
    losses = (df["result"] == "LOSS").sum()
    win_rate = wins / total * 100 if total else 0
    avg_win = df.loc[df["result"] == "WIN", "pnl_pct"].mean() if wins else 0
    avg_loss = df.loc[df["result"] == "LOSS", "pnl_pct"].mean() if losses else 0
    expectancy = (wins/total * avg_win) + (losses/total * avg_loss) if total else 0
    gp = df.loc[df["pnl_pct"] > 0, "pnl_pct"].sum()
    gl = abs(df.loc[df["pnl_pct"] < 0, "pnl_pct"].sum())
    pf = gp / gl if gl > 0 else 0
    equity = (1 + df["pnl_pct"] / 100).cumprod()
    dd = ((equity - equity.cummax()) / equity.cummax() * 100).min()
    avg_rr = df["rr"].mean() if "rr" in df else 0
    avg_days = df["days_held"].mean() if "days_held" in df else 0
    
    print(f"\n  {label}")
    print(f"    Trades:          {total}")
    print(f"    Wins/Losses:     {wins}/{losses}")
    print(f"    Win rate:        {win_rate:.1f}%")
    print(f"    Avg win:         +{avg_win:.2f}%")
    print(f"    Avg loss:        {avg_loss:.2f}%")
    print(f"    Expectancy:      +{expectancy:.2f}%/trade")
    print(f"    Profit factor:   {pf:.2f}")
    print(f"    Max drawdown:    {dd:.1f}%")
    print(f"    Avg R:R:         {avg_rr:.2f}" if "rr" in df else "")
    print(f"    Avg days held:   {avg_days:.1f}" if "days_held" in df else "")

# Exit reasons comparison
print(f"\n{'='*70}")
print(f"  EXIT REASONS")
print(f"{'='*70}")
print(f"  {'Reason':<20} {'v3 trades':>10} {'v3 avg%':>10} {'v2 trades':>10} {'v2 avg%':>10}")
print(f"  {'-'*65}")
for reason in sorted(set(v3["exit_reason"].unique()) | set(v2["exit_reason"].unique())):
    v3_sub = v3[v3["exit_reason"] == reason]
    v2_sub = v2[v2["exit_reason"] == reason]
    v3_avg = v3_sub["pnl_pct"].mean() if len(v3_sub) else 0
    v2_avg = v2_sub["pnl_pct"].mean() if len(v2_sub) else 0
    print(f"  {reason:<20} {len(v3_sub):>10} {v3_avg:>+9.2f}% {len(v2_sub):>10} {v2_avg:>+9.2f}%")

# By pattern comparison
print(f"\n{'='*70}")
print(f"  BY PATTERN")
print(f"{'='*70}")
print(f"  {'Pattern':<25} {'v3 n':>5} {'v3 WR':>7} {'v3 avg%':>8} {'v2 n':>5} {'v2 WR':>7} {'v2 avg%':>8}")
print(f"  {'-'*70}")
all_pats = sorted(set(v3["pattern"].unique()) | set(v2["pattern"].unique()))
for pat in all_pats:
    v3_sub = v3[v3["pattern"] == pat]
    v2_sub = v2[v2["pattern"] == pat]
    v3_wr = (v3_sub["result"] == "WIN").mean() * 100 if len(v3_sub) else 0
    v2_wr = (v2_sub["result"] == "WIN").mean() * 100 if len(v2_sub) else 0
    v3_avg = v3_sub["pnl_pct"].mean() if len(v3_sub) else 0
    v2_avg = v2_sub["pnl_pct"].mean() if len(v2_sub) else 0
    print(f"  {pat:<25} {len(v3_sub):>5} {v3_wr:>6.1f}% {v3_avg:>+7.2f}% {len(v2_sub):>5} {v2_wr:>6.1f}% {v2_avg:>+7.2f}%")

# Risk analysis
print(f"\n{'='*70}")
print(f"  RISK ANALYSIS (v3 fixed)")
print(f"{'='*70}")
if "stop_loss" in v3.columns and "entry_price" in v3.columns:
    v3_risk = (v3["entry_price"] - v3["stop_loss"]) / v3["entry_price"] * 100
    print(f"    Avg risk per trade:  {v3_risk.mean():.2f}%")
    print(f"    Max risk per trade:  {v3_risk.max():.2f}%")
    print(f"    Min risk per trade:  {v3_risk.min():.2f}%")
    print(f"    Trades >8% risk:     {(v3_risk > 8).sum()}/{len(v3)}")
    print(f"    Trades >10% risk:    {(v3_risk > 10).sum()}/{len(v3)}")
if "stop_loss" in v2.columns and "entry_price" in v2.columns:
    v2_risk = (v2["entry_price"] - v2["stop_loss"]) / v2["entry_price"] * 100
    print(f"\n  v2 (original):")
    print(f"    Avg risk per trade:  {v2_risk.mean():.2f}%")
    print(f"    Max risk per trade:  {v2_risk.max():.2f}%")
    print(f"    Trades >8% risk:     {(v2_risk > 8).sum()}/{len(v2)}")
    print(f"    Trades >10% risk:    {(v2_risk > 10).sum()}/{len(v2)}")

# Previous backtest comparison (from AGENTS.md)
print(f"\n{'='*70}")
print(f"  COMPARISON WITH PREVIOUS BACKTEST (from AGENTS.md)")
print(f"{'='*70}")
print(f"  {'Metric':<20} {'Previous v3':>15} {'Fixed v3':>15} {'Change':>10}")
print(f"  {'-'*60}")
print(f"  {'Trades':<20} {'2903':>15} {len(v3):>15} {len(v3)-2903:>+10}")
prev_wr = 42.6
print(f"  {'Win rate':<20} {prev_wr:>14.1f}% {38.0:>14.1f}% {38.0-prev_wr:>+9.1f}%")
prev_exp = 1.37
print(f"  {'Expectancy':<20} {prev_exp:>14.2f}% {1.32:>14.2f}% {1.32-prev_exp:>+9.2f}%")
prev_loss = -4.76
print(f"  {'Avg loss':<20} {prev_loss:>14.2f}% {-3.44:>14.2f}% {-3.44-prev_loss:>+9.2f}%")
print(f"  {'Avg win':<20} {'?':>15} {9.09:>14.2f}% {'':>10}")
print(f"  {'Profit factor':<20} {'?':>15} {1.62:>15.2f} {'':>10}")
