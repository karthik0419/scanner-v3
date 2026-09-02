"""Send entry-for-tomorrow list to Telegram."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_notify import send_telegram, _get_credentials

token, chat_id = _get_credentials()

msg = """<b>v3 Scanner — ENTRY LIST FOR TOMORROW</b>
<b>Date: 2026-08-04 (Monday)</b>

━━━━━━━━━━━━━━━━━━━
<b>BROKE OUT TODAY — ENTER AT OPEN</b>
━━━━━━━━━━━━━━━━━━━

<b>1. ABCAPITAL.NS</b> (Cup & Handle)
   Buy at/above: Rs 411.40
   Stop Loss:    Rs 392.16 (risk 4.7%)
   Target 1:     Rs 521.55 (+26.8%)
   Target 2:     Rs 631.69 (+53.6%)
   R:R:          1:5.73
   Today close:  Rs 424.35 (+3.15% above breakout)
   Volume:       3.9x avg (FIRE)

<b>2. NYKAA.NS</b> (Cup & Handle)
   Buy at/above: Rs 335.00
   Stop Loss:    Rs 321.19 (risk 4.1%)
   Target 1:     Rs 400.35 (+19.5%)
   Target 2:     Rs 465.70 (+39.0%)
   R:R:          1:4.73
   Today close:  Rs 344.90 (+2.96% above breakout)

<b>3. BPCL.NS</b> (Cup & Handle)
   Buy at/above: Rs 321.90
   Stop Loss:    Rs 306.19 (risk 4.9%)
   Target 1:     Rs 384.42 (+19.4%)
   Target 2:     Rs 446.95 (+38.9%)
   R:R:          1:3.98
   Today close:  Rs 329.95 (+2.50% above breakout)

<b>4. AVANTEL.NS</b> (Double Bottom)
   Buy at/above: Rs 162.55
   Stop Loss:    Rs 151.33 (risk 6.9%)
   Target 1:     Rs 185.30 (+14.0%)
   Target 2:     Rs 208.05 (+28.0%)
   R:R:          1:2.03
   Today close:  Rs 162.99 (+0.27% above breakout)

━━━━━━━━━━━━━━━━━━━
<b>WATCH — ENTER ONLY IF BREAKS ABOVE</b>
━━━━━━━━━━━━━━━━━━━

<b>5. PNB.NS</b> — Buy if crosses Rs 113.38
   SL: Rs 109.23 | T1: Rs 121.93 | T2: Rs 130.48
   Now: Rs 113.00 (-0.34% from breakout)

<b>6. TATAPOWER.NS</b> — Buy if crosses Rs 385.40
   SL: Rs 371.07 | T1: Rs 406.85 | T2: Rs 428.30
   Now: Rs 382.00 (-0.88% from breakout)

<b>7. RBLBANK.NS</b> — Buy if crosses Rs 383.45
   SL: Rs 364.00 | T1: Rs 483.23 | T2: Rs 583.00
   Now: Rs 379.95 (-0.91% from breakout)
   R:R: 1:5.13 (high reward if triggers)

<b>8. CASTROLIND.NS</b> — Buy if crosses Rs 188.95
   SL: Rs 179.24 | T1: Rs 209.27 | T2: Rs 229.60
   Now: Rs 185.84 (-1.65% from breakout)

━━━━━━━━━━━━━━━━━━━
<b>ALSO ACTIVE — GENESYS RE-ENTRY</b>
━━━━━━━━━━━━━━━━━━━
GENESYS.NS (Double Bottom re-entry)
   Entry: Rs 298.75 | SL: Rs 287.23 | T1: Rs 350.11 | T2: Rs 388.13
   Entered today, monitoring from tomorrow

━━━━━━━━━━━━━━━━━━━
<b>PRIORITY RANKING</b>
━━━━━━━━━━━━━━━━━━━
1. ABCAPITAL — best R:R (5.73), volume FIRE, sector hot (BANK)
2. NYKAA — good R:R (4.73), strong breakout
3. BPCL — solid R:R (3.98), energy sector
4. RBLBANK (watch) — highest R:R (5.13) if it triggers
5. AVANTEL — weakest R:R (2.03), highest risk (6.9%)

<b>Note:</b> Enter at breakout price, not current market price.
If gap up significantly, wait for pullback to breakout level.
Not financial advice. Paper trades for research."""

ok = send_telegram(token, chat_id, msg)
print("Telegram: %s" % ("Sent" if ok else "Failed"))
