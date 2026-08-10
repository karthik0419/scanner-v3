"""
Telegram Notifier — Weekly Swing Setup Scanner
Reads latest weekly results CSV and sends top setups to Telegram.

Usage:
  python telegram_notify.py               # auto-picks latest CSV
  python telegram_notify.py --top 15
  python telegram_notify.py --csv results/weekly_2026-05-18.csv

Can also be imported and called directly from other scripts:
  from telegram_notify import notify_scan_results, send_daily_summary
  notify_scan_results(csv_path, top=10)       # send weekly scan results
  send_daily_summary(summary_text)            # send daily scan summary
"""

import os, sys, argparse, glob
import pandas as pd
from datetime import date

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def _get_credentials():
    """Load Telegram token + chat_id from .env or environment. Returns (token, chat_id) or (None, None)."""
    env = load_env()
    token   = env.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_TOKEN") or \
              os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    return token, chat_id


def send_telegram(token, chat_id, text):
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram message limit is 4096 chars — split if needed
    if len(text) <= 4096:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        return resp.ok
    # Split into chunks at line boundaries
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 4000:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    ok = True
    for chunk in chunks:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        if not resp.ok:
            ok = False
    return ok


def format_message(df, top):
    """Format scan results for Telegram.

    Enhanced (2026-08-06) with learnings from chart analysis:
    - Target shown as T1 → T2 range on one line (e.g. "₹595 → ₹679")
    - % of measured move done / left (e.g. "12% done, 88% left")
    - Upside remaining from CMP (e.g. "+24.1% left to T2")
    - Flags: [S] Sustained, [N] Nested cup, [D] Double confirm
    - Historical resistance note if near T2 (~R2990)
    - Action line: BUY NOW vs BUY ABOVE ₹X
    """
    rows = df.head(top)
    medals = ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10."]

    lines = [
        f"<b>📊 SCANNER v3.1 — {date.today().strftime('%d %b %Y')}</b>",
        f"<b>Found: {len(df)} setups  |  Showing top {min(top, len(df))}</b>",
        "",
    ]

    for i, (_, row) in enumerate(rows.iterrows()):
        num   = medals[i] if i < len(medals) else f"{i+1}."
        sym   = str(row["symbol"]).replace(".NS", "")
        pat   = str(row["pattern"])
        score = row["score"]
        rr    = row["rr"]
        cmp   = row["cmp"]
        entry = row["breakout"]
        stop  = row["stop_loss"]
        t1    = row.get("target_1", row.get("target", 0))
        t2    = row.get("target_2", t1)
        status = str(row.get("status", ""))

        sector  = str(row.get("sector", ""))
        signal  = str(row.get("sector_signal", ""))
        tf      = str(row.get("timeframe", "Daily"))

        # New fields (may not exist in older CSVs — use .get with defaults)
        pct_done        = row.get("pct_done", 0)
        pct_left        = row.get("pct_left", 100)
        upside_rem      = row.get("upside_remaining", row.get("upside_%", 0))
        sustained       = str(row.get("sustained", "False")).lower() == "true"
        nested          = str(row.get("nested_cup", "False")).lower() == "true"
        double_confirm  = str(row.get("double_confirm", "False")).lower() == "true"
        hist_resist     = row.get("hist_resist", "")

        # Sector icon
        sec_icon = {"BOOM": "🔥", "RISING": "↑", "COOLING": "↓", "WEAK": "🔴"}.get(signal, "")

        # Flags string
        flag_parts = []
        if sustained:      flag_parts.append("[S]")
        if nested:         flag_parts.append("[N]")
        if double_confirm: flag_parts.append("[D]")
        flags = " ".join(flag_parts)

        # Historical resistance note
        resist_note = ""
        if hist_resist and str(hist_resist) not in ("", "nan", "0", "0.0"):
            try:
                resist_note = f"  ~prior resistance ₹{float(hist_resist):.0f}"
            except Exception:
                pass

        # Action line
        if status == "BREAKOUT":
            action = f"BUY NOW at ₹{cmp}"
        else:
            action = f"BUY above ₹{entry}"

        # Risk %
        risk_pct = round((entry - stop) / entry * 100, 1) if entry > 0 else 0

        msg_lines = [
            "━━━━━━━━━━━━━━━━━━━",
            f"{num} <b>{sym}</b>  Score {score}  {pat} [{tf}]  {flags}",
        ]

        # Sector line
        if sector and sector not in ("", "Unknown", "nan"):
            msg_lines.append(f"   🏭 {sector} {sec_icon} {signal}")

        # CMP + action
        msg_lines.append(f"   💰 CMP ₹{cmp}  →  {action}")

        # Stop + Target (T1→T2 on one line)
        t2_str = f" → ₹{t2}" if t2 and t2 != t1 else ""
        msg_lines.append(f"   🛑 SL ₹{stop} ({risk_pct}% risk)  |  🎯 Target ₹{t1}{t2_str}")

        # Move progress + upside remaining
        try:
            done_val = float(pct_done)
            left_val = float(pct_left)
            rem_val  = float(upside_rem)
            msg_lines.append(
                f"   📊 Move: {done_val:.0f}% done, {left_val:.0f}% left  |  +{rem_val:.1f}% to T2"
            )
        except Exception:
            pass

        # R:R
        msg_lines.append(f"   📈 R:R 1:{rr}")

        # Resist note
        if resist_note:
            msg_lines.append(f"   ⚠️{resist_note}")

        lines += msg_lines

    lines += [
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "<b>FLAGS:</b> [S]=Breakout sustained (10+ days)  [N]=Nested cup  [D]=Double confirm",
        "⚠️ For research only. Not financial advice.",
    ]
    return "\n".join(lines)


def notify_scan_results(csv_path=None, top=10, bearish=False):
    """Send scan results to Telegram. Callable from other scripts.

    Args:
        csv_path: path to results CSV. If None, auto-finds latest.
        top: number of top picks to send.
        bearish: if True, looks for v3_bearish_*.csv instead of v3_*.csv
    Returns True if sent, False if failed/skipped.
    """
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        print("  [Telegram] Missing credentials — skipping notification.")
        return False

    # Find CSV
    if csv_path is None:
        results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
        prefix = "v3_bearish" if bearish else "v3"
        files = [f for f in glob.glob(os.path.join(results_dir, f"{prefix}_*.csv")) if "_all" not in f]
        if not files:
            print("  [Telegram] No results CSV found — skipping notification.")
            return False
        files.sort(key=lambda f: os.path.getmtime(f))
        csv_path = files[-1]

    df = pd.read_csv(csv_path).sort_values("score", ascending=False)
    if df.empty:
        print("  [Telegram] No results to send.")
        return False

    msg = format_message(df, top)
    print(f"  [Telegram] Sending {len(df)} setups (top {top}) to Telegram...")
    if send_telegram(token, chat_id, msg):
        print("  [Telegram] Sent successfully.")
        return True
    else:
        print("  [Telegram] Failed to send.")
        return False


def send_daily_summary(summary_text, header=None):
    """Send a daily scan summary to Telegram. Callable from daily_scan.py.

    Args:
        summary_text: the text content to send (HTML formatted).
        header: optional header line (e.g. "DAILY SCAN — 17 Jul 2026").
    Returns True if sent, False if failed/skipped.
    """
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        print("  [Telegram] Missing credentials — skipping notification.")
        return False

    if header:
        msg = f"<b>{header}</b>\n━━━━━━━━━━━━━━━━━━━━━\n{summary_text}"
    else:
        msg = summary_text

    print("  [Telegram] Sending daily summary to Telegram...")
    if send_telegram(token, chat_id, msg):
        print("  [Telegram] Sent successfully.")
        return True
    else:
        print("  [Telegram] Failed to send.")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    token, chat_id = _get_credentials()
    if not token or not chat_id:
        print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in .env")
        sys.exit(1)

    # Find latest CSV (by modification time, not alphabetical)
    if args.csv:
        csv_path = args.csv
    else:
        results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
        # v3 produces v3_*.csv; also check v2_*.csv for backward compat
        files = [f for f in glob.glob(os.path.join(results_dir, "v3_*.csv")) if "_all" not in f]
        if not files:
            files = [f for f in glob.glob(os.path.join(results_dir, "v2_*.csv")) if "_all" not in f]
        if not files:
            print("No results CSV found. Run scanner.py first.")
            sys.exit(1)
        # Sort by modification time (newest last)
        files.sort(key=lambda f: os.path.getmtime(f))
        csv_path = files[-1]

    print(f"Reading: {csv_path}")
    df = pd.read_csv(csv_path).sort_values("score", ascending=False)

    if df.empty:
        print("No results to send.")
        sys.exit(0)

    msg = format_message(df, args.top)
    print("Sending to Telegram...")
    print(msg)

    if send_telegram(token, chat_id, msg):
        print("Sent successfully.")
    else:
        print("Failed to send.")
        sys.exit(1)


if __name__ == "__main__":
    main()
