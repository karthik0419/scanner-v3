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
    rows = df.head(top)
    medals = ["🥇", "🥈", "🥉"] + [f"{i+1}⃣" for i in range(3, top)]

    lines = [
        f"<b>📊 WEEKLY SWING SCAN — {date.today().strftime('%d %b %Y')}</b>",
        f"🔍 Scanned: Full NSE EQ (~2000+ stocks) | Found: {len(df)} setups",
        "",
    ]

    for i, (_, row) in enumerate(rows.iterrows()):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        sym   = str(row["symbol"]).replace(".NS", "")
        pat   = str(row["pattern"])
        score = row["score"]
        rr    = row["rr"]
        cmp   = row["cmp"]
        entry = row["breakout"]
        stop  = row["stop_loss"]
        tgt   = row.get("target_1", row.get("target", 0))
        up    = row["upside_%"]

        sector = str(row.get("sector",""))
        signal = str(row.get("sector_signal",""))
        neckline = str(row.get("neckline",""))
        sec_icon = "🔥" if signal=="BOOM" else "↑" if signal=="RISING" else "↓" if signal=="COOLING" else "🔴" if signal=="WEAK" else ""
        sec_line = f"🏭 {sector} {sec_icon} {signal}" if sector and sector not in ("","Unknown","nan") else ""
        neck_line = f"📐 Neckline: {neckline}" if neckline and neckline not in ("","nan") else ""

        msg_lines = [
            "━━━━━━━━━━━━━━━━━━━",
            f"{medal} <b>{sym}</b> | Score: {score} | {pat}",
        ]
        tf = str(row.get("timeframe", ""))
        if tf and tf not in ("", "nan"):
            msg_lines.append(f"📅 Timeframe: {tf}")
        if sec_line: msg_lines.append(sec_line)
        if neck_line: msg_lines.append(neck_line)
        msg_lines += [
            f"💰 CMP: ₹{cmp}  |  Entry: ₹{entry}",
            f"🛑 Stop: ₹{stop}  |  🎯 T1: ₹{tgt}",
            f"📈 Upside: {up}%  |  RR: {rr}x",
        ]
        lines += msg_lines

    lines += [
        "━━━━━━━━━━━━━━━━━━━",
        "",
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
        msg = f"<b>{header}</b>\n\n{summary_text}"
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
