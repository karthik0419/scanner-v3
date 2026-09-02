"""Send AVANTEL entry confirmation to Telegram."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_notify import send_telegram, _get_credentials

token, chat_id = _get_credentials()

msg = """<b>AVANTEL.NS — Position Entered & Tracker Updated</b>
<b>Date: 2026-08-04</b>

━━━━━━━━━━━━━━━━━━━
<b>YOUR POSITION</b>
━━━━━━━━━━━━━━━━━━━
  Pattern:    Double Bottom (v3 scanner)
  Entry:      Rs 162.55 (bought at breakout level)
  Stop Loss:  Rs 151.33 (risk: 6.9%, Rs 11.22/share)
  Target 1:   Rs 185.30 (+14.0%, profit Rs 22.75/share)
  Target 2:   Rs 208.05 (+28.0%, profit Rs 45.50/share)
  R:R:        1:2.03

━━━━━━━━━━━━━━━━━━━
<b>EXIT PLAN</b>
━━━━━━━━━━━━━━━━━━━
  - Exit 50% at T1: Rs 185.30 (+14.0%)
  - Exit 50% at T2: Rs 208.05 (+28.0%)
  - Hard stop: Rs 151.33 (-6.9%)

  If T1 hit: +Rs 22.75/share (partial)
  If T2 hit: +Rs 45.50/share (full)
  If stopped: -Rs 11.22/share

━━━━━━━━━━━━━━━━━━━
<b>PORTFOLIO TRACKER STATUS</b>
━━━━━━━━━━━━━━━━━━━
  AVANTEL.NS: WAITING_BREAKOUT -> OPEN
  Entry date: 2026-08-04
  Days held: 0

  Total tracker picks: 30
  OPEN (active): 15
  WAITING_BREAKOUT: 14
  Closed wins: 1

━━━━━━━━━━━━━━━━━━━
<b>ALL OPEN POSITIONS (15)</b>
━━━━━━━━━━━━━━━━━━━
  1.  NAZARA.NS      Entry 315.00  T1 364.15
  2.  SCI.NS         Entry 280.50  T1 322.98
  3.  FEDERALBNK.NS  Entry 358.70  T1 424.57
  4.  PATANJALI.NS   Entry 351.82  T1 413.14
  5.  VEDL.NS        Entry 259.35  T1 330.10
  6.  TATASTEEL.NS   Entry 186.92  T1 215.60
  7.  SURYODAY.NS    Entry 162.33  T1 184.51
  8.  MANAPPURAM.NS  Entry 363.00  T1 473.18
  9.  GOCOLORS.NS    Entry 323.00  T1 357.95
  10. GENESYS.NS     Entry 298.75  T1 350.11 (re-entry)
  11. AVANTEL.NS     Entry 162.55  T1 185.30 (NEW)
  12. SAIL.NS        Entry 165.85  T1 183.08
  13. RECLTD.NS      Entry 372.10  T1 450.67
  14. GAIL.NS        Entry 176.99  T1 232.96
  15. TATAMOTORS.NS  Entry 334.20  T1 363.95

━━━━━━━━━━━━━━━━━━━
Tracker will auto-monitor SL & targets daily.
Not financial advice. For research only."""

ok = send_telegram(token, chat_id, msg)
print("Telegram: %s" % ("Sent" if ok else "Failed"))
