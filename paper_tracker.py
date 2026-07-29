"""
Paper Trade Tracker for scanner-v3 picks.

Tracks today's scan results over time — no real money, just recording
what happens to the picks so we can validate the scanner live.

Usage:
  python paper_tracker.py init                    # init tracker from latest scan CSV
  python paper_tracker.py init --csv results/v3_2026-07-17.csv
  python paper_tracker.py update                  # fetch current prices, update status
  python paper_tracker.py update --price SYMBOL=PRICE --price SYMBOL2=PRICE2  # manual
  python paper_tracker.py status                  # show all trades + summary
  python paper_tracker.py summary                 # show just the summary stats
  python paper_tracker.py reset                   # clear tracker (careful!)

Tracker file: results/paper_tracker.csv
Each row = one pick, columns:
  symbol, pattern, status_at_scan, entry_price, stop_loss, target_1, target_2,
  scan_date, cmp_at_scan, risk_pct, upside_pct, rr, score, sector,
  current_price, current_status, current_pnl_pct, days_held, exit_price, exit_date, exit_reason
"""
import os
import sys
import argparse
import pandas as pd
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TRACKER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "results", "paper_tracker.csv"
)
RESULTS_DIR = os.path.dirname(TRACKER_PATH)

# ── Tradeability tiers ─────────────────────────────────────────────
def tradeability(risk_pct):
    if risk_pct < 1.0:
        return "SKIP_TIGHT"     # SL too close to CMP — noise will stop you out
    elif risk_pct <= 5.0:
        return "TRADE"          # standard swing risk
    elif risk_pct <= 8.0:
        return "TRADE_SMALL"    # wide SL — size down
    else:
        return "SKIP_WIDE"      # SL too far — too much capital at risk


# ── Init from scan CSV ──────────────────────────────────────────────
def init_tracker(csv_path=None):
    if csv_path is None:
        # Find latest v3_*.csv (not _all.csv)
        csvs = sorted(
            [f for f in os.listdir(RESULTS_DIR) if f.startswith("v3_") and f.endswith(".csv") and "_all" not in f],
            reverse=True,
        )
        if not csvs:
            print("No scan CSV found. Run scanner.py first or specify --csv.")
            return
        csv_path = os.path.join(RESULTS_DIR, csvs[0])

    df = pd.read_csv(csv_path)
    scan_date = date.today().isoformat()

    tracker = pd.DataFrame({
        "symbol":          df["symbol"],
        "pattern":         df["pattern"],
        "status_at_scan":  df["status"],
        "breakout_level":  df["breakout"],       # for NEAR picks — wait for breakout
        "entry_price":     df["cmp"],             # entry = CMP (BREAKOUT) or breakout price (NEAR, entered later)
        "stop_loss":       df["stop_loss"],
        "target_1":        df["target_1"],
        "target_2":        df["target_2"],
        "scan_date":       scan_date,
        "cmp_at_scan":     df["cmp"],
        "risk_pct":        df["risk_%"],
        "upside_pct":      df["upside_%"],
        "rr":              df["rr"],
        "score":           df["score"],
        "sector":          df.get("sector", ""),
        "current_price":   df["cmp"],             # initially same as entry
        "current_status":  "OPEN",                # BREAKOUT = OPEN immediately, NEAR = WAITING_BREAKOUT
        "current_pnl_pct": 0.0,
        "days_held":       0,
        "exit_price":      None,
        "exit_date":       None,
        "exit_reason":     None,
        "tradeable":       df["risk_%"].apply(tradeability),
    })

    # NEAR picks start as WAITING_BREAKOUT — only enter when price crosses breakout level
    # BREAKOUT picks start as OPEN — entered immediately at CMP
    # WATCH picks start as WATCH — not traded yet, waiting for NEAR/BREAKOUT
    tracker.loc[tracker["status_at_scan"] == "NEAR", "current_status"] = "WAITING_BREAKOUT"
    tracker.loc[tracker["status_at_scan"] == "WATCH", "current_status"] = "WATCH"
    tracker.loc[tracker["status_at_scan"] == "NEAR", "entry_price"] = tracker.loc[tracker["status_at_scan"] == "NEAR", "breakout_level"]

    tracker.to_csv(TRACKER_PATH, index=False)
    print(f"Tracker initialized: {TRACKER_PATH}")
    print(f"  {len(tracker)} picks from {os.path.basename(csv_path)}")
    print(f"  Scan date: {scan_date}")
    counts = tracker["tradeable"].value_counts()
    for tier, count in counts.items():
        print(f"  {tier}: {count}")
    print(f"\nRun 'python paper_tracker.py update' to fetch current prices.")


# ── Sync: merge new scan picks into existing tracker ─────────────────
def sync_tracker(csv_path=None):
    """Merge new scan results into the existing tracker.
    
    - New symbols (not in tracker) → added as new picks
    - Existing symbols still OPEN/WAITING_BREAKOUT → updated with latest scan data
      (new breakout level, new SL, new targets — in case the pattern evolved)
    - Existing symbols that are LOSS/WIN/TIME_EXIT → kept as-is (closed trades don't change)
    - Existing symbols that are RE_ENTERED → kept as-is (active re-entry trade)
    
    This is called automatically by scanner.py after each scan, or manually:
      python paper_tracker.py sync
      python paper_tracker.py sync --csv results/v3_2026-07-30.csv
    """
    if csv_path is None:
        csvs = sorted(
            [f for f in os.listdir(RESULTS_DIR) if f.startswith("v3_") and f.endswith(".csv") and "_all" not in f],
            reverse=True,
        )
        if not csvs:
            print("No scan CSV found. Run scanner.py first.")
            return
        csv_path = os.path.join(RESULTS_DIR, csvs[0])

    new_df = pd.read_csv(csv_path)
    scan_date = date.today().isoformat()

    # Build new picks dataframe
    new_picks = pd.DataFrame({
        "symbol":          new_df["symbol"],
        "pattern":         new_df["pattern"],
        "status_at_scan":  new_df["status"],
        "breakout_level":  new_df["breakout"],
        "entry_price":     new_df["cmp"],
        "stop_loss":       new_df["stop_loss"],
        "target_1":        new_df["target_1"],
        "target_2":        new_df["target_2"],
        "scan_date":       scan_date,
        "cmp_at_scan":     new_df["cmp"],
        "risk_pct":        new_df["risk_%"],
        "upside_pct":      new_df["upside_%"],
        "rr":              new_df["rr"],
        "score":           new_df["score"],
        "sector":          new_df.get("sector", ""),
        "current_price":   new_df["cmp"],
        "current_status":  "OPEN",
        "current_pnl_pct": 0.0,
        "days_held":       0,
        "exit_price":      None,
        "exit_date":       None,
        "exit_reason":     None,
        "tradeable":       new_df["risk_%"].apply(tradeability),
    })
    # Set initial status based on scan status
    new_picks.loc[new_picks["status_at_scan"] == "NEAR", "current_status"] = "WAITING_BREAKOUT"
    new_picks.loc[new_picks["status_at_scan"] == "WATCH", "current_status"] = "WATCH"
    new_picks.loc[new_picks["status_at_scan"] == "NEAR", "entry_price"] = new_picks.loc[new_picks["status_at_scan"] == "NEAR", "breakout_level"]

    if not os.path.exists(TRACKER_PATH):
        # No existing tracker — just init
        new_picks.to_csv(TRACKER_PATH, index=False)
        print(f"[SYNC] No existing tracker — initialized new one with {len(new_picks)} picks")
        return

    # Load existing tracker
    existing = pd.read_csv(TRACKER_PATH)
    
    # Statuses that are "closed" — don't touch these
    CLOSED = {"LOSS", "WIN_T1", "WIN_T2", "TIME_EXIT"}
    # Statuses that are "active" — update with new scan data
    ACTIVE = {"OPEN", "WAITING_BREAKOUT", "WATCH", "RE_ENTERED"}
    
    new_symbols = set(new_picks["symbol"])
    existing_symbols = set(existing["symbol"])
    
    added = 0
    updated = 0
    kept = 0
    
    # 1. New symbols not in tracker → add them
    to_add = new_picks[~new_picks["symbol"].isin(existing_symbols)]
    
    # 2. Existing symbols that are still active → update with latest scan data
    to_update_rows = []
    for idx, row in existing.iterrows():
        sym = row["symbol"]
        if sym in new_symbols and row["current_status"] in ACTIVE:
            # Update with new scan data but preserve current_status and trade progress
            new_row = new_picks[new_picks["symbol"] == sym].iloc[0].to_dict()
            # Keep the current status (don't reset WAITING_BREAKOUT to OPEN)
            # But update breakout level, SL, targets in case pattern evolved
            existing.at[idx, "breakout_level"] = new_row["breakout_level"]
            existing.at[idx, "stop_loss"] = new_row["stop_loss"]
            existing.at[idx, "target_1"] = new_row["target_1"]
            existing.at[idx, "target_2"] = new_row["target_2"]
            existing.at[idx, "score"] = new_row["score"]
            existing.at[idx, "pattern"] = new_row["pattern"]
            existing.at[idx, "status_at_scan"] = new_row["status_at_scan"]
            existing.at[idx, "cmp_at_scan"] = new_row["cmp_at_scan"]
            existing.at[idx, "risk_pct"] = new_row["risk_pct"]
            existing.at[idx, "upside_pct"] = new_row["upside_pct"]
            existing.at[idx, "rr"] = new_row["rr"]
            existing.at[idx, "sector"] = new_row["sector"]
            existing.at[idx, "scan_date"] = scan_date  # update scan date
            # If was WAITING_BREAKOUT and new scan says BREAKOUT → enter it
            if row["current_status"] == "WAITING_BREAKOUT" and new_row["status_at_scan"] == "BREAKOUT":
                existing.at[idx, "current_status"] = "OPEN"
                existing.at[idx, "entry_price"] = new_row["cmp_at_scan"]
                existing.at[idx, "days_held"] = 0
                print(f"  [SYNC-BREAKOUT] {sym} now BREAKOUT in new scan — entered at {new_row['cmp_at_scan']}")
            # If was WATCH and new scan says NEAR → upgrade to WAITING_BREAKOUT
            elif row["current_status"] == "WATCH" and new_row["status_at_scan"] in ("NEAR", "BREAKOUT"):
                existing.at[idx, "current_status"] = "WAITING_BREAKOUT" if new_row["status_at_scan"] == "NEAR" else "OPEN"
                if new_row["status_at_scan"] == "NEAR":
                    existing.at[idx, "entry_price"] = new_row["breakout_level"]
                print(f"  [SYNC-UPGRADE] {sym} upgraded from WATCH to {existing.at[idx, 'current_status']}")
            updated += 1
        elif sym in new_symbols and row["current_status"] in CLOSED:
            kept += 1  # closed trade, don't touch
        elif sym not in new_symbols and row["current_status"] in ACTIVE:
            kept += 1  # not in new scan but still active, keep tracking
        else:
            kept += 1
    
    # Combine: existing (with updates) + new picks
    if len(to_add) > 0:
        combined = pd.concat([existing, to_add], ignore_index=True)
        added = len(to_add)
    else:
        combined = existing
    
    combined.to_csv(TRACKER_PATH, index=False)
    print(f"[SYNC] Tracker updated from {os.path.basename(csv_path)}")
    print(f"  New picks added:    {added}")
    print(f"  Existing updated:   {updated}")
    print(f"  Kept as-is:         {kept}")
    print(f"  Total in tracker:   {len(combined)}")


# ── Update prices ───────────────────────────────────────────────────
def update_tracker(manual_prices=None):
    if not os.path.exists(TRACKER_PATH):
        print("No tracker found. Run 'python paper_tracker.py init' first.")
        return

    tracker = pd.read_csv(TRACKER_PATH)
    today = date.today()

    # Fetch current prices for open trades
    from data.loader import _fetch_nse

    updated = 0
    for idx, row in tracker.iterrows():
        if row["current_status"] in ("LOSS", "WIN_T1", "WIN_T2", "TIME_EXIT", "RE_ENTERED"):
            # Check if a STOPPED_OUT trade should re-enter (stock recovered above breakout)
            if row["current_status"] == "LOSS" and row.get("exit_reason") == "Stop Loss":
                breakout_level = float(row.get("breakout_level", 0) or 0)
                if breakout_level > 0:
                    sym = row["symbol"]
                    try:
                        df_temp = _fetch_nse(sym, days=5)
                        if df_temp is not None and not df_temp.empty:
                            cur_price = float(df_temp["Close"].iloc[-1])
                            scan_dt = datetime.fromisoformat(row["scan_date"]).date()
                            days_since_sl = (today - scan_dt).days
                            if days_since_sl <= 30 and cur_price >= breakout_level:
                                # Re-entry! Stock recovered above breakout after SL hit
                                tracker.at[idx, "current_status"] = "RE_ENTERED"
                                tracker.at[idx, "entry_price"] = round(breakout_level, 2)
                                tracker.at[idx, "stop_loss"] = round(breakout_level * 0.98, 2)  # tight 2% stop
                                tracker.at[idx, "current_price"] = round(cur_price, 2)
                                tracker.at[idx, "current_pnl_pct"] = 0.0
                                tracker.at[idx, "days_held"] = 0
                                tracker.at[idx, "exit_price"] = None
                                tracker.at[idx, "exit_date"] = None
                                tracker.at[idx, "exit_reason"] = None
                                updated += 1
                                print(f"  [RE-ENTRY] {sym} recovered to {cur_price:.2f} >= breakout {breakout_level:.2f}")
                    except Exception:
                        pass
            continue

        if row["current_status"] == "WATCH":
            continue  # not traded yet

        sym = row["symbol"]
        if manual_prices and sym in manual_prices:
            current_price = manual_prices[sym]
        else:
            try:
                df = _fetch_nse(sym, days=5)
                if df is not None and not df.empty:
                    current_price = float(df["Close"].iloc[-1])
                else:
                    continue
            except Exception:
                continue

        entry = float(row["entry_price"])
        stop = float(row["stop_loss"])
        t1 = float(row["target_1"])
        t2 = float(row["target_2"])
        breakout = float(row.get("breakout_level", 0) or 0)
        scan_dt = datetime.fromisoformat(row["scan_date"]).date()
        days_held = (today - scan_dt).days

        # WAITING_BREAKOUT: check if stock has broken out → enter trade
        if row["current_status"] == "WAITING_BREAKOUT":
            if current_price >= breakout:
                # Breakout confirmed! Enter the trade at breakout level
                tracker.at[idx, "current_status"] = "OPEN"
                tracker.at[idx, "entry_price"] = round(breakout, 2)
                tracker.at[idx, "days_held"] = 0
                entry = breakout  # update for P&L calc below
                print(f"  [BREAKOUT] {sym} broke out to {current_price:.2f} >= {breakout:.2f} — entered")
            else:
                # Still waiting for breakout
                tracker.at[idx, "current_price"] = round(current_price, 2)
                tracker.at[idx, "current_pnl_pct"] = round((current_price - breakout) / breakout * 100, 2)
                updated += 1
                continue

        pnl_pct = round((current_price - entry) / entry * 100, 2)

        # Determine status
        status = "OPEN"
        exit_price = None
        exit_date = None
        exit_reason = None

        if current_price <= stop:
            status = "LOSS"
            exit_price = stop
            exit_date = today.isoformat()
            exit_reason = "Stop Loss"
            pnl_pct = round((stop - entry) / entry * 100, 2)
        elif current_price >= t2:
            status = "WIN_T2"
            exit_price = t2
            exit_date = today.isoformat()
            exit_reason = "Target 2"
            pnl_pct = round((t2 - entry) / entry * 100, 2)
        elif current_price >= t1:
            status = "WIN_T1"
            # Don't close — T1 is partial exit in real trading, but we track
            # the full position here. Mark as "at T1" but still open for T2.
            exit_price = None
            exit_date = None
            exit_reason = None
        elif days_held >= 45:
            status = "TIME_EXIT"
            exit_price = current_price
            exit_date = today.isoformat()
            exit_reason = "Time Exit (45d)"

        tracker.at[idx, "current_price"] = round(current_price, 2)
        tracker.at[idx, "current_status"] = status
        tracker.at[idx, "current_pnl_pct"] = pnl_pct
        tracker.at[idx, "days_held"] = days_held
        if exit_price is not None:
            tracker.at[idx, "exit_price"] = round(exit_price, 2)
        if exit_date is not None:
            tracker.at[idx, "exit_date"] = exit_date
        if exit_reason is not None:
            tracker.at[idx, "exit_reason"] = exit_reason

        updated += 1

    tracker.to_csv(TRACKER_PATH, index=False)
    print(f"Updated {updated} open trades.")
    print(f"  Tracker: {TRACKER_PATH}")
    print(f"\nRun 'python paper_tracker.py status' to see results.")


# ── Show status ─────────────────────────────────────────────────────
def show_status():
    if not os.path.exists(TRACKER_PATH):
        print("No tracker found. Run 'python paper_tracker.py init' first.")
        return

    tracker = pd.read_csv(TRACKER_PATH)

    print("=" * 100)
    print(f"  PAPER TRADE TRACKER — scanner-v3")
    print(f"  Scan date: {tracker['scan_date'].iloc[0]} | Picks: {len(tracker)}")
    print("=" * 100)

    # Tradeable summary
    tradeable = tracker[tracker["tradeable"] != "SKIP_TIGHT"]
    tradeable = tradeable[tradeable["tradeable"] != "SKIP_WIDE"]

    open_trades = tracker[tracker["current_status"] == "OPEN"]
    closed = tracker[tracker["current_status"].isin(["LOSS", "WIN_T2", "TIME_EXIT"])]

    print(f"\n  OPEN: {len(open_trades)} | CLOSED: {len(closed)} | "
          f"TRADEABLE: {len(tradeable)} (excludes SKIP_TIGHT + SKIP_WIDE)")

    # Detail table
    print(f"\n  {'Symbol':<18} {'Pattern':<24} {'Entry':>8} {'SL':>8} {'T1':>8} "
          f"{'Now':>8} {'P&L%':>7} {'Days':>4} {'Status':<10} {'Tradeable'}")
    print("  " + "-" * 110)

    for _, row in tracker.iterrows():
        print(f"  {row['symbol']:<18} {row['pattern']:<24} "
              f"{row['entry_price']:>8.2f} {row['stop_loss']:>8.2f} {row['target_1']:>8.2f} "
              f"{row['current_price']:>8.2f} {row['current_pnl_pct']:>+6.2f}% "
              f"{row['days_held']:>4} {row['current_status']:<10} {row['tradeable']}")

    # Summary stats for closed trades
    if len(closed) > 0:
        print(f"\n{'='*100}")
        print(f"  CLOSED TRADES SUMMARY")
        print(f"{'='*100}")
        wins = closed[closed["current_pnl_pct"] > 0]
        losses = closed[closed["current_pnl_pct"] <= 0]
        total = len(closed)
        win_rate = len(wins) / total * 100 if total else 0
        avg_win = wins["current_pnl_pct"].mean() if len(wins) else 0
        avg_loss = losses["current_pnl_pct"].mean() if len(losses) else 0
        expectancy = (len(wins) / total * avg_win + len(losses) / total * avg_loss) if total else 0

        print(f"  Total closed: {total}")
        print(f"  Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"  Win rate: {win_rate:.1f}%")
        print(f"  Avg win: +{avg_win:.2f}% | Avg loss: {avg_loss:.2f}%")
        print(f"  Expectancy: {expectancy:+.2f}% per trade")

        # By exit reason
        print(f"\n  By exit reason:")
        for reason, group in closed.groupby("exit_reason"):
            print(f"    {reason:<20} {len(group):>3} trades | avg P&L: {group['current_pnl_pct'].mean():+.2f}%")

    # Open trades P&L (unrealized)
    if len(open_trades) > 0:
        print(f"\n{'='*100}")
        print(f"  OPEN TRADES — UNREALIZED P&L")
        print(f"{'='*100}")
        avg_unrealized = open_trades["current_pnl_pct"].mean()
        total_unrealized = open_trades["current_pnl_pct"].sum()
        winners = open_trades[open_trades["current_pnl_pct"] > 0]
        losers = open_trades[open_trades["current_pnl_pct"] <= 0]
        print(f"  Open trades: {len(open_trades)}")
        print(f"  In profit: {len(winners)} | In loss: {len(losers)}")
        print(f"  Avg unrealized P&L: {avg_unrealized:+.2f}%")
        print(f"  Sum unrealized P&L: {total_unrealized:+.2f}%")

    print(f"\n  Tracker file: {TRACKER_PATH}")
    print("=" * 100)


# ── Summary only ────────────────────────────────────────────────────
def show_summary():
    if not os.path.exists(TRACKER_PATH):
        print("No tracker found. Run 'python paper_tracker.py init' first.")
        return

    tracker = pd.read_csv(TRACKER_PATH)
    closed = tracker[tracker["current_status"].isin(["LOSS", "WIN_T2", "TIME_EXIT"])]
    open_trades = tracker[tracker["current_status"] == "OPEN"]

    print(f"\n  Paper Tracker Summary — scan date {tracker['scan_date'].iloc[0]}")
    print(f"  Total picks: {len(tracker)} | Open: {len(open_trades)} | Closed: {len(closed)}")

    if len(closed) > 0:
        wins = closed[closed["current_pnl_pct"] > 0]
        losses = closed[closed["current_pnl_pct"] <= 0]
        total = len(closed)
        wr = len(wins) / total * 100 if total else 0
        aw = wins["current_pnl_pct"].mean() if len(wins) else 0
        al = losses["current_pnl_pct"].mean() if len(losses) else 0
        exp = (len(wins) / total * aw + len(losses) / total * al) if total else 0
        print(f"  Closed: {total} | Win rate: {wr:.1f}% | Avg win: +{aw:.2f}% | Avg loss: {al:.2f}% | Expectancy: {exp:+.2f}%")

    if len(open_trades) > 0:
        avg_u = open_trades["current_pnl_pct"].mean()
        print(f"  Open: {len(open_trades)} | Avg unrealized: {avg_u:+.2f}%")


# ── Reset ───────────────────────────────────────────────────────────
def reset_tracker():
    if os.path.exists(TRACKER_PATH):
        confirm = input("This will DELETE the tracker. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            os.remove(TRACKER_PATH)
            print("Tracker deleted.")
        else:
            print("Cancelled.")
    else:
        print("No tracker to reset.")


# ── Main ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Paper Trade Tracker for scanner-v3")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize tracker from scan CSV")
    p_init.add_argument("--csv", default=None, help="Path to scan CSV (default: latest)")

    p_sync = sub.add_parser("sync", help="Merge new scan picks into existing tracker")
    p_sync.add_argument("--csv", default=None, help="Path to scan CSV (default: latest)")

    p_update = sub.add_parser("update", help="Update current prices + check breakouts + check re-entries")
    p_update.add_argument("--price", action="append", default=[],
                          help="Manual price: SYMBOL=PRICE (can repeat)")

    sub.add_parser("status", help="Show all trades + summary")
    sub.add_parser("summary", help="Show summary stats only")
    sub.add_parser("reset", help="Delete tracker")

    args = parser.parse_args()

    if args.command == "init":
        init_tracker(args.csv)
    elif args.command == "sync":
        sync_tracker(args.csv)
    elif args.command == "update":
        manual = {}
        for p in args.price:
            if "=" in p:
                sym, price = p.split("=", 1)
                manual[sym.strip()] = float(price.strip())
        update_tracker(manual if manual else None)
    elif args.command == "status":
        show_status()
    elif args.command == "summary":
        show_summary()
    elif args.command == "reset":
        reset_tracker()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
