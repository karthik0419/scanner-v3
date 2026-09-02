"""
Telegram alert for paper tracker — sends breakout/stop/target notifications.

Called by auto_tracker_update.bat after paper_tracker.py update.
Reads the tracker CSV, compares to the log file's last run, and sends
a Telegram message with:
  - New breakouts entered today (WAITING_BREAKOUT → OPEN)
  - New stop-loss hits (OPEN → LOSS)
  - New target hits (OPEN → WIN_T1 / WIN_T2)
  - Status of watched picks (AVANTEL, GLENMARK, etc.)

Usage:
  python tracker_alert.py                    # uses default .env
  python tracker_alert.py --env-file .env.swingiq   # uses SwingIQ channel
"""
import os
import sys
import argparse
import pandas as pd
from datetime import date, datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_notify import _get_credentials, send_telegram

TRACKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "results", "paper_tracker.csv")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LAST_RUN_PATH = os.path.join(LOG_DIR, "tracker_last_run.csv")

# Stocks we're actively watching (set alerts for these)
WATCHED = {"AVANTEL.NS", "GLENMARK.NS", "LAURUSLABS.NS", "YATHARTH.NS", "ANGELONE.NS", "STYRENIX.NS"}


def load_last_run():
    """Load the tracker state from the previous run (to detect changes)."""
    if not os.path.exists(LAST_RUN_PATH):
        return None
    try:
        return pd.read_csv(LAST_RUN_PATH)
    except Exception:
        return None


def save_current_run(df):
    """Save current tracker state for next run's comparison."""
    os.makedirs(LOG_DIR, exist_ok=True)
    df.to_csv(LAST_RUN_PATH, index=False)


def detect_changes(current, previous):
    """Compare current vs previous tracker state. Returns dict of changes."""
    changes = {
        "new_breakouts": [],   # WAITING_BREAKOUT → OPEN
        "new_losses": [],      # OPEN → LOSS
        "new_wins_t1": [],     # OPEN → WIN_T1
        "new_wins_t2": [],     # OPEN/WIN_T1 → WIN_T2
        "new_re_entries": [],  # LOSS → RE_ENTERED
        "new_waiting": [],     # newly added WAITING_BREAKOUT
    }

    if previous is None:
        # First run — just report current breakouts and watched stocks
        return changes

    # Build lookup: symbol → previous status
    prev_status = dict(zip(previous["symbol"], previous["current_status"]))
    prev_price = dict(zip(previous["symbol"], previous.get("current_price", [None]*len(previous))))

    for _, row in current.iterrows():
        sym = row["symbol"]
        curr_status = row["current_status"]
        prev = prev_status.get(sym)

        if prev is None:
            # New pick added
            if curr_status == "WAITING_BREAKOUT":
                changes["new_waiting"].append(row)
            continue

        if prev == curr_status:
            continue

        # Status changed — categorize
        if prev == "WAITING_BREAKOUT" and curr_status == "OPEN":
            changes["new_breakouts"].append(row)
        elif prev == "OPEN" and curr_status == "LOSS":
            changes["new_losses"].append(row)
        elif prev == "OPEN" and curr_status == "WIN_T1":
            changes["new_wins_t1"].append(row)
        elif curr_status == "WIN_T2":
            changes["new_wins_t2"].append(row)
        elif prev == "LOSS" and curr_status == "RE_ENTERED":
            changes["new_re_entries"].append(row)

    return changes


def build_message(current, changes):
    """Build the Telegram message text."""
    today = date.today().strftime("%Y-%m-%d")
    lines = [f"📊 <b>Paper Tracker Update</b> — {today}", ""]

    has_content = False

    # New breakouts
    if changes["new_breakouts"]:
        has_content = True
        lines.append(f"🟢 <b>NEW BREAKOUTS ({len(changes['new_breakouts'])})</b>")
        for r in changes["new_breakouts"]:
            lines.append(
                f"  {r['symbol']} → entered at ₹{r['entry_price']:.2f} "
                f"| SL ₹{r['stop_loss']:.2f} | T1 ₹{r['target_1']:.2f} "
                f"| R:R {r['rr']:.1f}x | {r['sector']}"
            )
        lines.append("")

    # Stop losses
    if changes["new_losses"]:
        has_content = True
        lines.append(f"🔴 <b>STOP LOSS HIT ({len(changes['new_losses'])})</b>")
        for r in changes["new_losses"]:
            lines.append(
                f"  {r['symbol']} → exited at ₹{r['exit_price']:.2f} "
                f"| P&L {r['current_pnl_pct']:+.1f}% | {r.get('exit_reason', 'SL')}"
            )
        lines.append("")

    # Target hits
    if changes["new_wins_t1"]:
        has_content = True
        lines.append(f"🟡 <b>TARGET 1 HIT ({len(changes['new_wins_t1'])})</b>")
        for r in changes["new_wins_t1"]:
            lines.append(
                f"  {r['symbol']} → ₹{r['current_price']:.2f} "
                f"| Holding for T2 ₹{r['target_2']:.2f}"
            )
        lines.append("")

    if changes["new_wins_t2"]:
        has_content = True
        lines.append(f"🟡 <b>TARGET 2 HIT ({len(changes['new_wins_t2'])})</b>")
        for r in changes["new_wins_t2"]:
            lines.append(
                f"  {r['symbol']} → closed at ₹{r['exit_price']:.2f} "
                f"| P&L {r['current_pnl_pct']:+.1f}%"
            )
        lines.append("")

    # Re-entries
    if changes["new_re_entries"]:
        has_content = True
        lines.append(f"🔵 <b>RE-ENTRIES ({len(changes['new_re_entries'])})</b>")
        for r in changes["new_re_entries"]:
            lines.append(
                f"  {r['symbol']} → re-entered at ₹{r['entry_price']:.2f} "
                f"| SL ₹{r['stop_loss']:.2f}"
            )
        lines.append("")

    # Watched stocks status (always show)
    watched_rows = current[current["symbol"].isin(WATCHED)]
    if len(watched_rows) > 0:
        has_content = True
        lines.append("👁 <b>WATCHED PICKS</b>")
        for _, r in watched_rows.iterrows():
            status_emoji = {
                "WAITING_BREAKOUT": "⏳",
                "OPEN": "✅",
                "LOSS": "❌",
                "WIN_T1": "🎯",
                "WIN_T2": "🏆",
            }.get(r["current_status"], "📍")
            if r["current_status"] == "WAITING_BREAKOUT":
                dist = ((r["breakout_level"] - r["current_price"]) / r["current_price"]) * 100
                lines.append(
                    f"  {status_emoji} {r['symbol']} → ₹{r['current_price']:.2f} "
                    f"| BO ₹{r['breakout_level']:.2f} ({dist:+.1f}%) "
                    f"| SL ₹{r['stop_loss']:.2f} ({r['risk_pct']:.1f}% risk)"
                )
            elif r["current_status"] == "OPEN":
                lines.append(
                    f"  {status_emoji} {r['symbol']} → ₹{r['current_price']:.2f} "
                    f"| P&L {r['current_pnl_pct']:+.1f}% | Days {r['days_held']}"
                )
            else:
                lines.append(
                    f"  {status_emoji} {r['symbol']} → {r['current_status']} "
                    f"| P&L {r['current_pnl_pct']:+.1f}%"
                )
        lines.append("")

    # Summary line
    open_count = len(current[current["current_status"] == "OPEN"])
    waiting_count = len(current[current["current_status"] == "WAITING_BREAKOUT"])
    closed = current[current["current_status"].isin(["LOSS", "WIN_T1", "WIN_T2", "TIME_EXIT"])]
    wins = len(closed[closed["current_status"].isin(["WIN_T1", "WIN_T2"])])
    losses = len(closed[closed["current_status"] == "LOSS"])
    wr = (wins / len(closed) * 100) if len(closed) > 0 else 0

    lines.append(f"📈 Open: {open_count} | Waiting: {waiting_count} | "
                 f"Closed: {len(closed)} (W:{wins} L:{losses} WR:{wr:.0f}%)")

    if not has_content:
        lines.insert(2, "No new breakouts or exits today.")
        lines.insert(3, "")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Send paper tracker Telegram alert")
    parser.add_argument("--env-file", default=None, help="Env file for Telegram credentials")
    args = parser.parse_args()

    if not os.path.exists(TRACKER_PATH):
        print("No tracker file found. Run paper_tracker.py update first.")
        return

    current = pd.read_csv(TRACKER_PATH)
    previous = load_last_run()
    changes = detect_changes(current, previous)

    msg = build_message(current, changes)
    print(msg)
    print()

    # Send to Telegram
    token, chat_id = _get_credentials(args.env_file)
    if token and chat_id:
        ok = send_telegram(token, chat_id, msg)
        if ok:
            print("[ALERT] Telegram message sent successfully.")
        else:
            print("[ALERT] Telegram send FAILED (check token/chat_id).")
    else:
        print("[ALERT] No Telegram credentials — message printed above only.")

    # Save current state for next run comparison
    save_current_run(current)
    print(f"[ALERT] Saved current state to {LAST_RUN_PATH}")


if __name__ == "__main__":
    main()
