import pandas as pd

# Load Scanner-v3's actual backtest results
df = pd.read_csv('results/backtest_v3_reentry.csv')

print("=" * 100)
print("SCANNER-V3 ACTUAL BACKTEST RESULTS (from backtest_v3_reentry.csv)")
print("=" * 100)
print()

total_trades = len(df)
winners = df[df['pnl_pct'] > 0]
losers = df[df['pnl_pct'] < 0]

win_rate = len(winners) / total_trades * 100
avg_win = winners['pnl_pct'].mean()
avg_loss = losers['pnl_pct'].mean()
avg_pnl = df['pnl_pct'].mean()

expectancy = (len(winners)/total_trades * avg_win) + (len(losers)/total_trades * avg_loss)

gross_profit = winners['pnl_pct'].sum()
gross_loss = abs(losers['pnl_pct'].sum())
profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

# Max drawdown
df_sorted = df.sort_values('exit_date')
df_sorted['cumulative_pnl'] = df_sorted['pnl_pct'].cumsum()
df_sorted['running_max'] = df_sorted['cumulative_pnl'].cummax()
df_sorted['drawdown'] = df_sorted['cumulative_pnl'] - df_sorted['running_max']
max_dd = df_sorted['drawdown'].min()

print(f"Total trades: {total_trades}")
print(f"Winners: {len(winners)} ({win_rate:.1f}%)")
print(f"Losers: {len(losers)} ({100 - win_rate:.1f}%)")
print()
print(f"Avg win: {avg_win:+.2f}%")
print(f"Avg loss: {avg_loss:+.2f}%")
print(f"Avg P&L: {avg_pnl:+.2f}%")
print()
print(f"Expectancy: {expectancy:+.2f}%")
print(f"Profit factor: {profit_factor:.2f}")
print(f"Max drawdown: {max_dd:.2f}%")
print()

# Pattern breakdown
print("Pattern breakdown:")
if 'pattern' in df.columns:
    for pattern in df['pattern'].unique():
        pattern_df = df[df['pattern'] == pattern]
        pattern_win_rate = len(pattern_df[pattern_df['pnl_pct'] > 0]) / len(pattern_df) * 100
        pattern_avg_pnl = pattern_df['pnl_pct'].mean()
        print(f"  {pattern:30} {len(pattern_df):4} trades | Win rate: {pattern_win_rate:5.1f}% | Avg P&L: {pattern_avg_pnl:+6.2f}%")
print()

# Exit reasons
print("Exit reasons:")
if 'exit_reason' in df.columns:
    for reason, count in df['exit_reason'].value_counts().items():
        pct = count / total_trades * 100
        avg_pnl_reason = df[df['exit_reason'] == reason]['pnl_pct'].mean()
        print(f"  {reason:15} {count:4} ({pct:5.1f}%) | Avg P&L: {avg_pnl_reason:+.2f}%")
print()

print("=" * 100)
print("COMPARISON")
print("=" * 100)
print()

print("Scanner-v3 PROVEN (from AGENTS.md):")
print("  Trades: 3012")
print("  Win rate: 40.6%")
print("  Avg win: +7.6%")
print("  Avg loss: -3.0%")
print("  Expectancy: +1.30%")
print("  Profit factor: 1.73")
print("  Max drawdown: -60.1%")
print()

print("Scanner-v3 ACTUAL (from backtest_v3_reentry.csv):")
print(f"  Trades: {total_trades}")
print(f"  Win rate: {win_rate:.1f}%")
print(f"  Avg win: {avg_win:+.2f}%")
print(f"  Avg loss: {avg_loss:+.2f}%")
print(f"  Expectancy: {expectancy:+.2f}%")
print(f"  Profit factor: {profit_factor:.2f}")
print(f"  Max drawdown: {max_dd:.2f}%")
print()

print("My 'Garbage' Combined Backtest:")
print("  Trades: 1828")
print("  Win rate: 24.5%")
print("  Avg win: +10.20%")
print("  Avg loss: -3.12%")
print("  Expectancy: +0.15%")
print("  Profit factor: 1.06")
print("  Max drawdown: -823.55%")
print()

print("=" * 100)
print("VERDICT")
print("=" * 100)
print()

if abs(expectancy - 1.30) < 0.20 and abs(profit_factor - 1.73) < 0.20:
    print("*** ACTUAL BACKTEST MATCHES PROVEN RESULTS! ***")
    print()
    print("Scanner-v3's pattern detection is EXCELLENT!")
    print("My 'garbage' backtest WAS garbage!")
elif expectancy > 1.0:
    print("ACTUAL BACKTEST is close to proven results")
    print()
    print(f"Expectancy: {expectancy:+.2f}% vs +1.30% (proven)")
    print(f"Profit factor: {profit_factor:.2f} vs 1.73 (proven)")
else:
    print("ACTUAL BACKTEST differs from proven results")
    print()
    print("Possible reasons:")
    print("  - Different stock universe")
    print("  - Different time period")
    print("  - Different parameters")
