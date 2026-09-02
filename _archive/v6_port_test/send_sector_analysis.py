"""Send sector + regime analysis to Telegram."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_notify import send_telegram, _get_credentials

token, chat_id = _get_credentials()

msg = """<b>Momentum Strategy — Sector + Regime Analysis (5 years)</b>
<b>Capital: Rs 50,000 | Period: 60 months | NSE EQ ~2000 stocks</b>

━━━━━━━━━━━━━━━━━━━
<b>THE PROBLEM</b>
━━━━━━━━━━━━━━━━━━━
Baseline (no filter): Rs 50k -> Rs 19k (-61.8%)
The strategy LOSES money over full market cycles.

━━━━━━━━━━━━━━━━━━━
<b>SECTOR BREAKDOWN</b>
━━━━━━━━━━━━━━━━━━━
<b>PROFITABLE sectors (8):</b>
  Auto: 48 trades, 60.4% WR, +Rs 5,234
  Media: 17 trades, 76.5% WR, +Rs 5,175
  Telecom: 7 trades, 57.1% WR, +Rs 1,951
  Energy: 31 trades, 61.3% WR, +Rs 1,875
  Chemicals: 62 trades, 53.2% WR, +Rs 1,842
  Diversified: 2 trades, 100% WR, +Rs 1,448
  Services: 17 trades, 58.8% WR, +Rs 880
  Pharma: 40 trades, 52.5% WR, +Rs 618

<b>LOSING sectors (11):</b>
  Infra: 146 trades, 50% WR, -Rs 12,769 (WORST)
  Realty: 27 trades, 33.3% WR, -Rs 9,279
  Textiles: 36 trades, 38.9% WR, -Rs 8,176
  Banking: 17 trades, 35.3% WR, -Rs 4,087
  Metals: 44 trades, 50% WR, -Rs 4,059
  Financial Services: 37 trades, 45.9% WR, -Rs 3,861
  Consumer Durables: 28 trades, 46.4% WR, -Rs 3,387

<b>Key insight:</b> Infra alone lost Rs 12,769 — more than the entire portfolio.
146 trades (22% of all trades) came from Infra and they were net negative.

━━━━━━━━━━━━━━━━━━━
<b>REAL-TIME FILTERS (no look-ahead bias)</b>
━━━━━━━━━━━━━━━━━━━
Regime = Nifty 50 above/below SMA50 + SMA200
(checkable in real-time, no hindsight)

<b>Config                          Trades   Final      Return   CAGR</b>
Baseline (no filter)               673   Rs 19,089   -61.8%   -17.5%
Top 5 sectors only                 165   Rs 61,759   +23.5%   +4.3%
BULL regime only (SMA50)           394   Rs 43,560   -12.9%   -2.7%
Top 5 + BULL (SMA50)               101   Rs 60,271   +20.5%   +3.8%
<b>Top 5 + BULL (SMA50+200)          93   Rs 63,482   +27.0%   +4.9%</b>
Top 3 + BULL (SMA50)                47   Rs 57,817   +15.6%   +2.9%
Exclude worst 5 + BULL (SMA50)     236   Rs 56,054   +12.1%   +2.3%
Exclude worst 5 + BULL (SMA50+200) 223   Rs 62,912   +25.8%   +4.7%
Bank FD (7% annual)                --    Rs 67,500   +35.0%   +7.0%

━━━━━━━━━━━━━━━━━━━
<b>VERDICT</b>
━━━━━━━━━━━━━━━━━━━
<b>Best combo: Top 5 sectors + BULL regime (SMA50+200)</b>
  +27% over 5 years = 4.9% CAGR
  93 trades, 63.4% win rate

<b>BUT Bank FD at 7% CAGR beats ALL combinations.</b>

Sector filtering DOES save the strategy from blowing up (-61% -> +27%),
but even the best version (4.9% CAGR) underperforms a bank FD (7%).

<b>The momentum strategy is NOT tradeable even with sector + regime filters.</b>

━━━━━━━━━━━━━━━━━━━
<b>WHY IT FAILS</b>
━━━━━━━━━━━━━━━━━━━
1. Avg loss (-7.7%) > avg win (+6.2%) — negative expectancy per trade
2. 51.3% win rate is barely above coin flip — not enough to overcome the loss>win asymmetry
3. Sector filter helps (removes Infra/Realty/Textiles bleeders) but can't fix the core math
4. Regime filter helps (avoids bear quarters) but bull quarters still have bad stretches
5. The 6-month positive result was pure luck (strong momentum regime)

━━━━━━━━━━━━━━━━━━━
<b>WHAT TO DO INSTEAD</b>
━━━━━━━━━━━━━━━━━━━
Stick with v3.1 (pattern-based scanner):
  - +1.30% expectancy/trade, PF 1.73, 40.6% win rate
  - Avg loss -3.0% (vs momentum's -7.7%) — much tighter risk
  - 3012 trades validated over 2 years
  - The edge comes from CHART PATTERNS, not momentum continuation

<b>Do NOT implement the momentum strategy. v3.1 is the better edge.</b>

━━━━━━━━━━━━━━━━━━━
Realistic: next-day entry, slippage, brokerage, STT, liquidity filter.
Regime filter uses Nifty SMA50+200 (real-time, no look-ahead).
Sector filter uses NSE official sector map.
Not financial advice. For research only."""

ok = send_telegram(token, chat_id, msg)
print(f"Telegram: {'Sent' if ok else 'Failed'}")
