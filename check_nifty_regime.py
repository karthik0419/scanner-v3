import yfinance as yf
import pandas as pd

# Download Nifty 50 data
nifty = yf.download('^NSEI', period='2y', progress=False)

# Flatten MultiIndex columns if present (newer yfinance returns MultiIndex
# even for single tickers, which breaks scalar indexing downstream).
if isinstance(nifty.columns, pd.MultiIndex):
    nifty.columns = nifty.columns.get_level_values(0)

# Calculate SMAs
nifty['SMA50'] = nifty['Close'].rolling(50).mean()
nifty['SMA200'] = nifty['Close'].rolling(200).mean()

# Get latest values (force scalar via float())
close = float(nifty['Close'].iloc[-1])
sma50 = float(nifty['SMA50'].iloc[-1])
sma200 = float(nifty['SMA200'].iloc[-1])
prev_close = float(nifty['Close'].iloc[-5]) if len(nifty) >= 5 else close

print("=" * 60)
print("NIFTY 50 MARKET REGIME CHECK")
print("=" * 60)
print(f"\nCurrent Price: {close:.2f}")
print(f"SMA 50:        {sma50:.2f}")
print(f"SMA 200:       {sma200:.2f}")
print(f"\nPrice vs SMA50:  {'+' if close > sma50 else '-'}{abs(close - sma50):.2f} ({((close / sma50 - 1) * 100):.2f}%)")
print(f"Price vs SMA200: {'+' if close > sma200 else '-'}{abs(close - sma200):.2f} ({((close / sma200 - 1) * 100):.2f}%)")
print(f"SMA50 vs SMA200: {'+' if sma50 > sma200 else '-'}{abs(sma50 - sma200):.2f} ({((sma50 / sma200 - 1) * 100):.2f}%)")

# Weekly change
weekly_change = ((close / prev_close - 1) * 100)
print(f"\nWeekly Change: {weekly_change:+.2f}%")

# Regime determination
above_50 = close > sma50
above_200 = close > sma200
golden_cross = sma50 > sma200

print("\n" + "=" * 60)
if above_50 and above_200 and golden_cross:
    print("REGIME: 🟢 BULL MARKET (All conditions met)")
    print("✅ Price > SMA50")
    print("✅ Price > SMA200")
    print("✅ SMA50 > SMA200 (Golden Cross)")
    print("\n✅ SAFE TO SCAN - Market is supportive")
elif above_50 and above_200:
    print("REGIME: 🟡 CAUTIOUS BULL (Price above SMAs, but no golden cross)")
    print("✅ Price > SMA50")
    print("✅ Price > SMA200")
    print("❌ SMA50 < SMA200 (Death Cross)")
    print("\n⚠️  SCAN WITH CAUTION - Market is mixed")
elif above_200:
    print("REGIME: 🟡 CHOPPY (Price above 200 DMA but below 50 DMA)")
    print("❌ Price < SMA50")
    print("✅ Price > SMA200")
    print("\n⚠️  AVOID SCANNING - Market is choppy")
else:
    print("REGIME: 🔴 BEAR MARKET (Price below 200 DMA)")
    print("❌ Price < SMA50")
    print("❌ Price < SMA200")
    print("\n🛑 DO NOT SCAN - Market is bearish")

print("=" * 60)

# Recent trend
print("\nLast 10 Days:")
recent = nifty.tail(10)[['Close', 'SMA50', 'SMA200']].copy()
recent['Above_50'] = recent['Close'] > recent['SMA50']
recent['Above_200'] = recent['Close'] > recent['SMA200']
print(recent.to_string())
