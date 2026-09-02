"""Send TECHM analysis to Telegram."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_notify import send_telegram, _get_credentials

token, chat_id = _get_credentials()

msg = """<b>TECHM.NS — Position Analysis</b>
<b>Date: 2026-08-04</b>

━━━━━━━━━━━━━━━━━━━
<b>YOUR POSITION</b>
━━━━━━━━━━━━━━━━━━━
  Entry:    Rs 1,589.00 x 20 qty
  Invested: Rs 31,780
  Current:  Rs 1,647.90
  P&L:      +3.71% (Rs +1,178)
  Value:    Rs 32,958

━━━━━━━━━━━━━━━━━━━
<b>V3 SCANNER HISTORY</b>
━━━━━━━━━━━━━━━━━━━
TECHM was picked by v3 scanner:
  Jul 16: Double Bottom NEAR, score 49.6
  Jul 17: Double Bottom NEAR, score 62.6
  Jul 18: Double Bottom NEAR, score 77.5

Your entry (Rs 1,589) = scanner breakout level
Pattern: Double Bottom
  Breakout: Rs 1,589
  Stop:     Rs 1,513.54 (Jul 18 scan)
  T1:       Rs 1,746.02 (+9.9% from entry)
  T2:       Rs 1,850.70 (+16.4% from entry)

━━━━━━━━━━━━━━━━━━━
<b>TREND: BULLISH</b>
━━━━━━━━━━━━━━━━━━━
  Price > 20-day SMA (Rs 1,549) -> ABOVE
  Price > 50-day SMA (Rs 1,471) -> ABOVE
  20-day SMA > 50-day SMA       -> BULLISH CROSS
  Distance from 50-day high:    -2.29% (near highs!)
  IT sector today:              +3.28% (HOT)

━━━━━━━━━━━━━━━━━━━
<b>KEY LEVELS</b>
━━━━━━━━━━━━━━━━━━━
  Resistance: Rs 1,686.60 (50-day high)
  T1 target:  Rs 1,746.02 (+9.9% from entry)
  T2 target:  Rs 1,850.70 (+16.4% from entry)
  Current:    Rs 1,647.90 (+3.7% from entry)
  20-day SMA: Rs 1,548.97 (support)
  Trailing SL:Rs 1,559.16 (2x ATR from current)
  Original SL:Rs 1,513.54 (from scanner)

━━━━━━━━━━━━━━━━━━━
<b>RECENT PRICE ACTION</b>
━━━━━━━━━━━━━━━━━━━
  Jul 28: +2.26% (breakout day, 5M vol)
  Jul 29: -1.01% (pullback)
  Jul 30: +1.21% (recovered, hit 1686 high)
  Jul 31: +1.93% (strong close 1651)
  Aug 04: -0.30% (consolidation, low vol)

Stock broke out on Jul 28 with 5M volume (2x avg),
pulled back, then made new 50-day high on Jul 30.
Now consolidating near highs — healthy action.

━━━━━━━━━━━━━━━━━━━
<b>RECOMMENDATION: HOLD</b>
━━━━━━━━━━━━━━━━━━━
<b>DO NOT EXIT — this is a winning trade in progress.</b>

Reasons to hold:
  1. Trend is BULLISH (price > 20SMA > 50SMA)
  2. Only 2.3% from 50-day high — momentum intact
  3. IT sector is HOT (+3.28% today)
  4. T1 target (Rs 1,746) is +6.0% away
  5. T2 target (Rs 1,851) is +12.3% away
  6. Stock was v3 scanner pick (score 77.5)

<b>SUGGESTED EXIT PLAN:</b>
  - Trail stop to Rs 1,559 (locks ~breakeven)
  - Exit 50% (10 qty) at T1: Rs 1,746 (+9.9%)
  - Exit 50% (10 qty) at T2: Rs 1,851 (+16.4%)
  - Hard stop: Rs 1,514 (original scanner SL)

  If T1 hit: profit = Rs 1,570 (full 20 qty)
  If T2 hit: profit = Rs 2,617 (full 20 qty)
  If stopped: loss = Rs -1,509 (20 qty)

  R:R = 1:1.74 to T1 (acceptable)
  R:R = 1:2.90 to T2 (good)

<b>Only exit NOW if:</b>
  - Price breaks below Rs 1,514 (scanner stop)
  - IT sector reverses sharply
  - You need the capital urgently

━━━━━━━━━━━━━━━━━━━
Not financial advice. For research only."""

ok = send_telegram(token, chat_id, msg)
print("Telegram: %s" % ("Sent" if ok else "Failed"))
