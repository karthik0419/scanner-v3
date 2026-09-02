"""Check VEEDOL.NS status and recommendation"""
import pandas as pd
import yfinance as yf
from utils.sector_rotation_v3 import get_stock_sector
from utils.regime import get_market_regime

# Load tracker
df = pd.read_csv('results/paper_tracker.csv')
veedol = df[df['symbol'] == 'VEEDOL.NS']

print("=" * 80)
print("VEEDOL.NS - HOLD OR EXIT ANALYSIS")
print("=" * 80)

if len(veedol) == 0:
    print("VEEDOL.NS not found in tracker")
    exit()

row = veedol.iloc[0]
sector = get_stock_sector('VEEDOL.NS')

print("\nCURRENT POSITION:")
print("-" * 80)
print(f"Symbol:        {row['symbol']}")
print(f"Sector:        {sector}")
print(f"Pattern:       {row['pattern']}")
print(f"Entry:         Rs {row['entry_price']:.2f}")
print(f"Stop Loss:     Rs {row['stop_loss']:.2f}")
print(f"Target 1:      Rs {row['target_1']:.2f}")
print(f"Target 2:      Rs {row['target_2']:.2f}")
print(f"Current Price: Rs {row['current_price']:.2f}")
print(f"P&L:           {row['current_pnl_pct']:.2f}%")
print(f"Days Held:     {row['days_held']}")
print(f"Status:        {row['current_status']}")
print(f"Tradeable:     {row['tradeable']}")

# Calculate distances
dist_to_sl = ((row['current_price'] - row['stop_loss']) / row['current_price']) * 100
dist_to_t1 = ((row['target_1'] - row['current_price']) / row['current_price']) * 100
dist_to_t2 = ((row['target_2'] - row['current_price']) / row['current_price']) * 100

print(f"\nDistance to SL:  {dist_to_sl:.2f}% away")
print(f"Distance to T1:  {dist_to_t1:.2f}% away")
print(f"Distance to T2:  {dist_to_t2:.2f}% away")

# Market regime
print("\n" + "=" * 80)
print("MARKET CONTEXT:")
print("-" * 80)

regime = get_market_regime()
if regime:
    print(f"Market Status: {regime['status']}")
    print(f"HOT Sectors:   {', '.join(regime.get('strong_sectors', []))}")
    
    if sector in regime.get('strong_sectors', []):
        print(f"\nVEEDOL Sector ({sector}): HOT SECTOR - Good for holding")
    else:
        print(f"\nVEEDOL Sector ({sector}): WEAK SECTOR - Consider exiting")

# Get latest price
print("\n" + "=" * 80)
print("LATEST PRICE CHECK:")
print("-" * 80)

try:
    ticker = yf.Ticker('VEEDOL.NS')
    hist = ticker.history(period='5d')
    if len(hist) > 0:
        latest = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else latest
        change = ((latest - prev) / prev) * 100
        
        print(f"Latest Price:  Rs {latest:.2f}")
        print(f"Change:        {change:+.2f}%")
        print(f"Volume:        {hist['Volume'].iloc[-1]:,.0f}")
        
        # Update P&L with latest price
        latest_pnl = ((latest - row['entry_price']) / row['entry_price']) * 100
        print(f"Latest P&L:    {latest_pnl:.2f}%")
        
        # Check if near SL
        if latest <= row['stop_loss']:
            print("\nWARNING: Price at or below stop loss!")
except Exception as e:
    print(f"Could not fetch latest price: {e}")

# Decision framework
print("\n" + "=" * 80)
print("DECISION FRAMEWORK:")
print("=" * 80)

reasons_to_exit = []
reasons_to_hold = []

# Check sector
if sector not in ['Pharma', 'IT', 'FMCG']:
    reasons_to_exit.append(f"Sector ({sector}) is WEAK - not in HOT list")
else:
    reasons_to_hold.append(f"Sector ({sector}) is HOT")

# Check P&L
if row['current_pnl_pct'] < 0:
    reasons_to_exit.append(f"Losing position ({row['current_pnl_pct']:.2f}%)")
else:
    reasons_to_hold.append(f"Profitable position ({row['current_pnl_pct']:.2f}%)")

# Check distance to SL
if dist_to_sl < 2:
    reasons_to_exit.append(f"Very close to SL ({dist_to_sl:.2f}% away)")
elif dist_to_sl > 5:
    reasons_to_hold.append(f"Good cushion from SL ({dist_to_sl:.2f}% away)")

# Check market regime
if regime and regime['status'] == 'BEAR':
    reasons_to_exit.append("Market is BEAR - difficult for breakouts")
elif regime and regime['status'] == 'BULL':
    reasons_to_hold.append("Market is BULL - good for breakouts")

# Check days held
if row['days_held'] > 20:
    reasons_to_exit.append(f"Held too long ({row['days_held']} days) - not moving")

print("\nREASONS TO EXIT:")
if reasons_to_exit:
    for i, reason in enumerate(reasons_to_exit, 1):
        print(f"  {i}. {reason}")
else:
    print("  None")

print("\nREASONS TO HOLD:")
if reasons_to_hold:
    for i, reason in enumerate(reasons_to_hold, 1):
        print(f"  {i}. {reason}")
else:
    print("  None")

# Final recommendation
print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)

exit_score = len(reasons_to_exit)
hold_score = len(reasons_to_hold)

if exit_score > hold_score:
    print("\nEXIT - More reasons to exit than hold")
    print(f"Exit Score: {exit_score} | Hold Score: {hold_score}")
    print(f"\nSuggested Action: Exit at market price (Rs {row['current_price']:.2f})")
    print(f"Expected P&L: {row['current_pnl_pct']:.2f}%")
elif hold_score > exit_score:
    print("\nHOLD - More reasons to hold than exit")
    print(f"Exit Score: {exit_score} | Hold Score: {hold_score}")
    print(f"\nSuggested Action: Keep holding, watch for T1 (Rs {row['target_1']:.2f})")
    print(f"Stop Loss: Rs {row['stop_loss']:.2f}")
else:
    print("\nNEUTRAL - Equal reasons to hold/exit")
    print(f"Exit Score: {exit_score} | Hold Score: {hold_score}")
    print(f"\nSuggested Action: Your choice - slight preference to EXIT in BEAR market")

print("\n" + "=" * 80)
