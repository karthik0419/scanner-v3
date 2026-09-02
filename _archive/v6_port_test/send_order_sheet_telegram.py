"""
Send the Monday Order Sheet (2026-07-20) summary + all charts to Telegram.
Uses the same .env credentials as telegram_notify.py.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_notify import _get_credentials, send_telegram

CHARTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "results", "charts", "ordersheet_2026-07-20",
)

ORDER = [
    ("INDIANB",    "820-832",   "795.30",   "946.90",   "-",        "9-10",  "earnings +30.6% YoY (already above trigger)"),
    ("MPHASIS",    "cross 2479","2357.24",  "2758.60",  "-",        "3",     "best RR 9.86x"),
    ("ZAGGLE",     "cross 213.86","203.58", "230.55",   "241.67",   "28",    "Financial Services RISING"),
    ("EMKAY",      "cross 253.80","236.37", "294.48",   "321.60",   "23",    "Financial Services RISING alt (pick ONE of ZAGGLE/EMKAY)"),
    ("TECHM",      "cross 1589", "1513.54", "1746.02",  "-",        "4",     "IT RISING"),
    ("NATCOPHARM", "cross 960.40","918.52", "1063.24",  "1131.80",  "6",     "cross w/ volume"),
    ("PIRAMALFIN", "cross 2220", "2032.42", "2552.94",  "2774.90",  "3",     "both scanners, likely later in week"),
]

HEADER = (
    "<b>📋 MONDAY ORDER SHEET — 20 Jul 2026</b>\n"
    "🔴 <b>REGIME: RISK_OFF</b> (Nifty 2% below 200DMA)\n"
    "Half-size positions | Max 3 fills | SL immediately after fill\n"
    "━━━━━━━━━━━━━━━━━━━"
)

def _row(i, sym, buy, sl, t1, t2, qty, note):
    t2_line = f"\n   🎯 T2: ₹{t2}" if t2 != "-" else ""
    return (
        f"\n<b>{i}. {sym}</b>  ({note})\n"
        f"   💰 BUY: ₹{buy}\n"
        f"   🛑 SL: ₹{sl}   |   🎯 T1: ₹{t1}{t2_line}\n"
        f"   📦 Qty: {qty} sh"
    )

SUMMARY = HEADER
for i, (sym, buy, sl, t1, t2, qty, note) in enumerate(ORDER, 1):
    SUMMARY += _row(i, sym, buy, sl, t1, t2, qty, note)
SUMMARY += (
    "\n━━━━━━━━━━━━━━━━━━━\n"
    "💸 Deployed: ~₹34-40k | Worst case: ~₹1,900 (under 2%)\n"
    "\n<b>RULES</b>\n"
    "• 9:15-9:45: do nothing, let open settle\n"
    "• Volume must be over 1.5x avg at trigger\n"
    "• Skip if gap over 2% above entry\n"
    "• SL order the moment buy fills (GTT OCO)\n"
    "• T1 hit: sell 50%, move SL to entry\n"
    "• Never widen an SL\n"
    "• Flat 3-4 weeks: time exit\n"
    "\n⚠️ For research only. Not financial advice."
)


def send_photo(token, chat_id, path, caption):
    import requests
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(path, "rb") as f:
        files = {"photo": f}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, files=files, data=data, timeout=60)
    return resp.ok


def main():
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in .env")
        sys.exit(1)

    print("Sending order-sheet summary...")
    if not send_telegram(token, chat_id, SUMMARY):
        print("Failed to send summary.")
        sys.exit(1)
    print("Summary sent.\n")

    # Send charts: Daily first, then Weekly, grouped per symbol
    for sym, buy, sl, t1, t2, qty, note in ORDER:
        for tf in ("daily", "weekly"):
            path = os.path.join(CHARTS_DIR, f"{sym}_{tf}.png")
            if not os.path.exists(path):
                print(f"  Missing: {path}")
                continue
            cap = f"📊 <b>{sym}</b> [{tf.upper()}]\nBUY ₹{buy} | SL ₹{sl} | T1 ₹{t1}"
            if t2 != "-":
                cap += f" | T2 ₹{t2}"
            ok = send_photo(token, chat_id, path, cap)
            print(f"  {sym} [{tf}]: {'sent' if ok else 'FAILED'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
