# Paper Tracker - Example Output with Market Regime

## 🎯 HOW IT WILL LOOK

### **When Market Data is Available:**

```
====================================================================================================
  PAPER TRADE TRACKER — scanner-v3
  Scan date: 2026-08-10 | Picks: 243
====================================================================================================

  MARKET: 🔴 BEAR | Nifty: 24,192 | 200 DMA: 24,677
  HOT Sectors: 🔥 Pharma, IT, FMCG

  OPEN: 73 | CLOSED: 13 | TRADEABLE: 230 (excludes SKIP_TIGHT + SKIP_WIDE)

  ⚠️  WARNING: 50 open trades in WEAK sectors (not in HOT list)
  Consider exiting these - they may struggle in current market:
    - RELIANCE      (Energy      ) P&L: -2.50%
    - TATAMOTORS    (Auto        ) P&L: -2.26%
    - DLF           (Realty      ) P&L: -1.80%
    - VEDL          (Metals      ) P&L: +5.53%
    - SAIL          (Metals      ) P&L: +3.59%
    ... and 45 more

  Symbol             Pattern                     Entry       SL       T1      Now    P&L% Days Status
  -------------------------------------------------------------------------------------------------------
  PNB.NS             Cup & Handle               113.38   112.19   133.18   116.63  +2.87%    8 OPEN
  SCI.NS             Double Bottom              280.50   263.09   322.98   290.75  +3.65%   19 OPEN
  DEVYANI.NS         Cup & Handle               124.00   116.04   146.94   142.10 +14.60%   18 OPEN
  ...
```

---

### **When yfinance is Rate-Limited (Current):**

```
====================================================================================================
  PAPER TRADE TRACKER — scanner-v3
  Scan date: 2026-08-10 | Picks: 243
====================================================================================================
  OPEN: 73 | CLOSED: 13 | TRADEABLE: 230 (excludes SKIP_TIGHT + SKIP_WIDE)

  Symbol             Pattern                     Entry       SL       T1      Now    P&L% Days Status
  -------------------------------------------------------------------------------------------------------
  PNB.NS             Cup & Handle               113.38   112.19   133.18   116.63  +2.87%    8 OPEN
  ...
```

*(Market regime info doesn't show when data unavailable - this is normal)*

---

## ✅ WHAT WAS ADDED TO PAPER TRACKER

### **1. Market Regime Display** (Lines 397-413)
```python
# Market regime info
try:
    from utils.regime import get_market_regime
    regime = get_market_regime()
    if regime:
        status = regime["status"]
        hot_sectors = regime.get("strong_sectors", [])
        nifty = regime["close"]
        sma200 = regime["sma200"]
        
        status_emoji = {"BULL": "🟢", "CHOPPY": "🟡", "BEAR": "🔴"}.get(status, "⚪")
        print(f"\n  MARKET: {status_emoji} {status} | Nifty: {nifty:,.0f} | 200 DMA: {sma200:,.0f}")
        if hot_sectors:
            print(f"  HOT Sectors: 🔥 {', '.join(hot_sectors)}")
        print()
except Exception:
    pass
```

**Shows**:
- Market status: BULL 🟢 / CHOPPY 🟡 / BEAR 🔴
- Nifty level
- 200 DMA level
- HOT sectors list

---

### **2. Weak Sector Warning** (Lines 425-452)
```python
# Sector breakdown for open trades (if market is weak)
if len(open_trades) > 0:
    try:
        from utils.regime import get_market_regime
        from utils.sector_rotation_v3 import get_stock_sector
        regime = get_market_regime()
        if regime and regime["status"] in ["CHOPPY", "BEAR"]:
            hot_sectors = regime.get("strong_sectors", [])
            if hot_sectors:
                # Count open trades by sector
                sector_counts = {}
                weak_sector_trades = []
                for _, row in open_trades.iterrows():
                    sym = row["symbol"]
                    sector = get_stock_sector(sym if sym.endswith(".NS") else sym + ".NS")
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1
                    if sector not in hot_sectors:
                        weak_sector_trades.append((sym, sector, row["current_pnl_pct"]))
                
                if weak_sector_trades:
                    print(f"\n  ⚠️  WARNING: {len(weak_sector_trades)} open trades in WEAK sectors")
                    print(f"  Consider exiting these - they may struggle in current market:")
                    for sym, sector, pnl in weak_sector_trades[:5]:
                        print(f"    - {sym:<15} ({sector:<12}) P&L: {pnl:+.2f}%")
                    if len(weak_sector_trades) > 5:
                        print(f"    ... and {len(weak_sector_trades) - 5} more")
    except Exception:
        pass
```

**Shows**:
- Count of weak sector trades
- List of up to 5 weak sector trades
- Sector name + current P&L for each
- Only shows in CHOPPY/BEAR markets

---

## 🎯 WHEN IT SHOWS

| Market | Regime Display | Weak Sector Warning |
|--------|---------------|---------------------|
| **BULL** | ✅ Shows (if data available) | ❌ No warning (all sectors work) |
| **CHOPPY** | ✅ Shows (if data available) | ✅ Shows (if weak sector trades exist) |
| **BEAR** | ✅ Shows (if data available) | ✅ Shows (if weak sector trades exist) |
| **Rate Limited** | ❌ Doesn't show | ❌ Doesn't show |

---

## 💡 WHAT TO DO

### **If You See This:**
```
MARKET: 🔴 BEAR | Nifty: 24,192 | 200 DMA: 24,677
HOT Sectors: 🔥 Pharma, IT, FMCG

⚠️  WARNING: 50 open trades in WEAK sectors
  - RELIANCE      (Energy      ) P&L: -2.50%
  - TATAMOTORS    (Auto        ) P&L: -2.26%
  ...
```

**Action**:
1. ✅ Review the weak sector trades list
2. ✅ Consider exiting trades with negative P&L
3. ✅ Keep trades with positive P&L (but watch closely)
4. ✅ Don't take new trades in weak sectors
5. ✅ Focus new trades on HOT sectors only

---

### **If You Don't See Market Info:**
```
====================================================================================================
  PAPER TRADE TRACKER — scanner-v3
  Scan date: 2026-08-10 | Picks: 243
====================================================================================================
  OPEN: 73 | CLOSED: 13 | TRADEABLE: 230
```

**Reason**: yfinance is rate-limited (too many API calls)

**Solution**: 
- Wait 10-15 minutes
- Or check market regime manually:
  ```powershell
  .\Daily Scan.bat
  Select: 26 (Check which sectors are HOT today)
  ```

---

## ✅ SUMMARY

**What**: Paper tracker shows market regime + warns about weak sector trades

**When**: Every time you run `python paper_tracker.py status` (if data available)

**Why**: Helps you manage risk in weak markets

**Action**: Consider exiting weak sector trades in CHOPPY/BEAR markets

**File Updated**: `paper_tracker.py` (lines 397-452)

**No Breaking Changes**: All existing functionality works as before ✅
