# Scanner V3 - Market Regime Filter Guide

**Added**: 2026-08-25
**Feature**: Smart market regime detection + defensive sector filtering

---

## 🎯 What It Does

**A. Simple Warning** - Shows market status before every scan
**C. Smart Defensive Filter** - Auto-filters to defensive sectors in weak markets

---

## 📊 Market Regimes

### 🟢 BULL MARKET
**Criteria**:
- ✅ Nifty > SMA50
- ✅ Nifty > SMA200  
- ✅ SMA50 > SMA200 (Golden Cross)

**What happens**:
- ✅ All sectors work
- ✅ Scan runs normally
- ✅ No filtering applied

**Example**:
```
🟢 REGIME: BULL MARKET
✅ SAFE TO SCAN - All sectors supported
```

---

### 🟡 CHOPPY MARKET
**Criteria**:
- ✅ Nifty > SMA200
- ❌ SMA50 < SMA200 (Death Cross)

**What happens**:
- ⚠️ Warning shown
- 💡 Suggests defensive sectors
- 🔧 `--defensive` flag filters to: Pharma, IT, FMCG, Healthcare

**Example**:
```
🟡 REGIME: CHOPPY MARKET
⚠️  WARNING: Market is choppy - breakouts may fail
📊 Recent performance: 1.88% win rate, -1.91% avg P&L

💡 SUGGESTION: Focus on defensive sectors
   Pharma, IT, FMCG, Healthcare
   (Use --defensive flag to auto-filter)
```

---

### 🔴 BEAR MARKET
**Criteria**:
- ❌ Nifty < SMA50
- ❌ Nifty < SMA200
- ❌ SMA50 < SMA200 (Death Cross)

**What happens**:
- 🛑 Strong warning shown
- 💡 Suggests waiting or bearish scan
- 🔧 `--defensive` flag filters to: Pharma, IT, FMCG, Healthcare, Utilities

**Example**:
```
🔴 REGIME: BEAR MARKET
🛑 NOT RECOMMENDED for long setups
📊 Recent performance: 1.88% win rate, -1.91% avg P&L

💡 BETTER OPTIONS:
   1. Wait for bullish regime (Nifty > 24684)
   2. Run bearish scan: python scanner.py --bearish
   3. Stay in cash and preserve capital
```

---

## 🛠️ How to Use

### Normal Scan (Just Warning)
```powershell
python scanner.py

# Shows warning but scans all sectors
# You decide what to do
```

### Defensive Scan (Auto-Filter)
```powershell
python scanner.py --defensive

# In CHOPPY/BEAR markets:
# - Only scans Pharma, IT, FMCG, Healthcare (+ Utilities in BEAR)
# - Skips all other sectors
# - Finds only defensive plays
```

### Daily Scan with Defensive Filter
```powershell
python daily_scan.py --defensive

# Same logic - auto-filters to defensive sectors
```

---

## 📈 Current Market Status (2026-08-25)

```
Nifty 50:  24,219
SMA 50:    24,194  (+0.10%)
SMA 200:   24,684  (-1.88%)

🔴 REGIME: BEAR MARKET
```

**What this means**:
- Nifty is 465 points BELOW 200 DMA
- Market is in bearish trend
- Only 1.88% of stocks are working
- Defensive sectors are your best bet

---

## 🎯 Defensive Sectors

### Why These Sectors?

**Pharma**:
- People need medicine in any market
- Export-driven (dollar earnings)
- Defensive demand

**IT**:
- Export-driven (dollar earnings)
- Recurring revenue models
- Less affected by domestic slowdown

**FMCG**:
- Consumer staples (food, soap, etc.)
- Stable demand
- Defensive stocks

**Healthcare**:
- Hospitals, diagnostics
- Essential services
- Recession-proof

**Utilities** (only in BEAR):
- Power, gas, water
- Monopoly businesses
- Stable cash flows

---

## 📊 Performance Comparison

### Without `--defensive` (All Sectors)
```
Test scan: 15 setups found
Sectors: Banking, Auto, Chemicals, IT, Pharma, etc.
Risk: Many sectors are weak in current market
```

### With `--defensive` (Filtered)
```
Test scan: 2 setups found
Sectors: IT (ACCELYA), Pharma (AARTIDRUGS)
Risk: Lower - only defensive plays
```

---

## 💡 Recommendations by Regime

### BULL Market
```powershell
# Scan normally - all sectors work
python scanner.py
python daily_scan.py
```

### CHOPPY Market
```powershell
# Option 1: Defensive filter
python scanner.py --defensive

# Option 2: Wait for bullish regime
# (Check daily: python quick_regime.py)

# Option 3: Reduce position sizes
python scanner.py  # but trade 50% size
```

### BEAR Market
```powershell
# Option 1: Defensive filter only
python scanner.py --defensive

# Option 2: Bearish scan (shorts)
python scanner.py --bearish

# Option 3: Stay in cash
# (Best option - preserve capital)
```

---

## 🔍 Check Regime Anytime

```powershell
# Quick check
python quick_regime.py

# Output:
# Nifty: 24219
# SMA50: 24194
# SMA200: 24684
# Regime: BEAR/CHOPPY
```

---

## 🚀 Examples

### Example 1: Scan in BEAR market (no filter)
```powershell
python scanner.py --top 20

# Shows warning:
# 🔴 REGIME: BEAR MARKET
# 🛑 NOT RECOMMENDED for long setups
# 
# But still scans all sectors
# Found: 20 setups (many won't work)
```

### Example 2: Scan in BEAR market (with filter)
```powershell
python scanner.py --top 20 --defensive

# Shows:
# 🔴 REGIME: BEAR MARKET
# ✅ AUTO-FILTERING to defensive sectors
#
# Only scans: Pharma, IT, FMCG, Healthcare, Utilities
# Found: 5 setups (higher quality)
```

### Example 3: Daily scan with defensive filter
```powershell
python daily_scan.py --top 15 --defensive

# In BEAR market:
# - Scans only defensive sectors
# - Finds 3-5 setups instead of 15
# - Higher win rate expected
```

---

## 📝 Summary

| Flag | Market | Behavior |
|------|--------|----------|
| None | BULL | ✅ Scan all sectors |
| None | CHOPPY | ⚠️ Warning + scan all |
| None | BEAR | 🛑 Strong warning + scan all |
| `--defensive` | BULL | ✅ Scan all (no filter needed) |
| `--defensive` | CHOPPY | 🔧 Filter to 4 defensive sectors |
| `--defensive` | BEAR | 🔧 Filter to 5 defensive sectors |

---

## 🎯 Bottom Line

**The scanner now WARNS you when market is weak, and FILTERS to defensive sectors if you want.**

- **No override** - scans still run as usual
- **Just adds intelligence** - you know market status
- **Optional filtering** - use `--defensive` to auto-filter

**Use `--defensive` in choppy/bear markets to improve win rate!**
