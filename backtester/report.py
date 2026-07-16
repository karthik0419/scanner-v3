"""
Backtest report generator v3 — enhanced with T1/T2 split reporting,
trailing stop stats, and expectancy calculation.
"""
import pandas as pd
import numpy as np


def generate_report(trades, output_csv="backtest_results.csv"):
    if not trades:
        print("No trades to report.")
        return pd.DataFrame()

    df = pd.DataFrame(trades)
    df.to_csv(output_csv, index=False)

    total = len(df)
    wins = (df["result"] == "WIN").sum()
    losses = (df["result"] == "LOSS").sum()
    win_rate = wins / total * 100 if total > 0 else 0

    avg_win = df.loc[df["result"] == "WIN", "pnl_pct"].mean() if wins else 0
    avg_loss = df.loc[df["result"] == "LOSS", "pnl_pct"].mean() if losses else 0
    avg_pnl = df["pnl_pct"].mean()

    gross_profit = df.loc[df["pnl_pct"] > 0, "pnl_pct"].sum()
    gross_loss = abs(df.loc[df["pnl_pct"] < 0, "pnl_pct"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Expectancy
    win_rate_dec = wins / total if total > 0 else 0
    loss_rate_dec = losses / total if total > 0 else 0
    expectancy = (win_rate_dec * avg_win) + (loss_rate_dec * avg_loss)

    # Max drawdown (equity curve)
    equity = (1 + df["pnl_pct"] / 100).cumprod()
    peak = equity.cummax()
    drawdown = ((equity - peak) / peak * 100).min()

    # Avg days held
    avg_days = df["days_held"].mean() if "days_held" in df.columns else 0

    print("\n" + "=" * 65)
    print("BACKTEST REPORT — v3")
    print("=" * 65)
    print(f"Total Trades    : {total}")
    print(f"Wins            : {wins}  ({win_rate:.1f}%)")
    print(f"Losses          : {losses}  ({100 - win_rate:.1f}%)")
    print(f"Avg Win         : +{avg_win:.2f}%")
    print(f"Avg Loss        : {avg_loss:.2f}%")
    print(f"Avg P&L / Trade : {avg_pnl:.2f}%")
    print(f"Profit Factor   : {profit_factor:.2f}")
    print(f"Expectancy      : {expectancy:+.2f}% per trade")
    print(f"Max Drawdown    : {drawdown:.2f}%")
    print(f"Avg Days Held   : {avg_days:.1f}")

    # --- By Pattern ---
    print("\n--- By Pattern ---")
    pat = (
        df.groupby("pattern")
        .apply(
            lambda g: pd.Series({
                "Trades": len(g),
                "Wins": (g["result"] == "WIN").sum(),
                "Win%": f"{(g['result'] == 'WIN').mean()*100:.1f}%",
                "Avg P&L": f"{g['pnl_pct'].mean():.2f}%",
                "Best": f"{g['pnl_pct'].max():.2f}%",
                "Worst": f"{g['pnl_pct'].min():.2f}%",
            }),
            include_groups=False,
        )
        .reset_index()
    )
    print(pat.to_string(index=False))

    # --- By Exit Reason ---
    print("\n--- By Exit Reason ---")
    ex = (
        df.groupby("exit_reason")
        .apply(
            lambda g: pd.Series({
                "Trades": len(g),
                "Avg P&L": f"{g['pnl_pct'].mean():.2f}%",
            }),
            include_groups=False,
        )
        .reset_index()
    )
    print(ex.to_string(index=False))

    # --- By Year ---
    if "entry_date" in df.columns:
        df["year"] = pd.to_datetime(df["entry_date"]).dt.year
        print("\n--- By Year ---")
        yr = (
            df.groupby("year")
            .apply(
                lambda g: pd.Series({
                    "Trades": len(g),
                    "Win%": f"{(g['result'] == 'WIN').mean()*100:.1f}%",
                    "Avg P&L": f"{g['pnl_pct'].mean():.2f}%",
                }),
                include_groups=False,
            )
            .reset_index()
        )
        print(yr.to_string(index=False))

    print(f"\nFull results saved to: {output_csv}")
    return df
