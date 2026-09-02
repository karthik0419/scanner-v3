"""Send market summary to Telegram"""
import os
from dotenv import load_dotenv
import requests

# Load SwingIQ bot credentials
load_dotenv('.env.swingiq')

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

message = """
🔴 BEAR MARKET ALERT - 25 Aug 2026

📊 MARKET STATUS:
• Nifty: 24,132 (below 200 DMA)
• Regime: BEAR MARKET
• HOT Sectors: Pharma, IT, FMCG (all down today)

⚠️ TODAY'S SCAN: 0 SETUPS FOUND
• Scanned 467 stocks (HOT sectors only)
• No quality setups in current market
• All HOT sectors are down today

💡 RECOMMENDATION: STAY IN CASH

✅ WHAT TO DO:
1. Hold existing winners (SUNDRMFAST +9.95%)
2. Stay in cash for new entries
3. Wait for market to turn BULL
4. Monitor daily for regime change

📉 RECENT PERFORMANCE:
• Win rate: 23% (vs 40% expected)
• Avg P&L: -1.91% in BEAR market
• Better to preserve capital

🎯 WHEN TO ENTER:
• Wait for Nifty > 24,676 (200 DMA)
• Wait for HOT sectors to turn green
• Wait for BULL regime confirmation

💰 CURRENT PORTFOLIO:
• 48 open trades (avg +2.71%)
• Exited 25 weak sector trades today
• Portfolio cleaned and ready

Stay patient. Cash is a position! 💵
"""

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
data = {
    "chat_id": CHAT_ID,
    "text": message,
    "parse_mode": "HTML"
}

response = requests.post(url, data=data)
if response.status_code == 200:
    print("Message sent to Telegram (SwingIQ)")
else:
    print(f"Failed to send: {response.text}")
