# Paper Tracker - Market Regime Integration

**Updated**: 2026-08-25
**Feature**: Shows market regime + HOT sectors + warns about weak sector trades

---

## 🎯 WHAT WAS ADDED

### 1. Market Regime Display
Shows current market status at the top of tracker:
```
MARKET: 🔴 BEAR | Nifty: 24,192 | 200 DMA: 24,677
HOT Sectors: 🔥 Pharma, IT, FMCG
```

### 2. Weak Sector Warning
If market is CHOPPY/BEAR and you have open trades in weak sectors:
```
⚠️  WARNING: 15 open trades in WEAK sectors (not in HOT list)
Consider exiting these - they may struggle in current market:
  - RELIANCE      (Energy      ) P&L: -2.50%
  - TATAMOTORS    (Auto        ) P&L: -3.20%
  - DLF           (Realty      ) P&L: -1.80%
  ... and 12 more
```

---

## 📊 HOW IT LOOKS

### Before (Old):
```
====================================================================================================
  PAPER TRADE TRACKER — scanner-v3
  Scan date: 2026-08-10 | Picks: 243
====================================================================================================
  OPEN: 73 | CLOSED: 13 | TRADEABLE: 230

  Symbol             Pattern                     Entry       SL       T1      Now    P&L%
  --------------------------------------------------------------------------------------
  PNB.NS             Cup & Handle               113.38   112.19   133.18   116.63  +2.87%
  ...
```

### After (New):
```
====================================================================================================
  PAPER TRADE TRACKER — scanner-v3
  Scan date: 2026-08-10 | Picks: 243
====================================================================================================

  MARKET: 🔴 BEAR | Nifty: 24,192 | 200 DMA: 24,677
  HOT Sectors: 🔥 Pharma, IT, FMCG

  OPEN: 73 | CLOSED: 13 | TRADEABLE: 230

  ⚠️  WARNING: 15 open trades in WEAK sectors (not in HOT list)
  Consider exiting these - they may struggle in current market:
    - RELIANCE      (Energy      ) P&L: -2.50%
    - TATAMOTORS    (Auto        ) P&L: -3.20%
    - DLF           (Realty      ) P&L: -1.80%
    ... and 12 more

  Symbol             Pattern                     Entry       SL       T1      Now    P&L%
  --------------------------------------------------------------------------------------
  PNB.NS             Cup & Handle               113.38   112.19   133.18   116.63  +2.87%
  ...
```

---

## 🎯 WHEN IT SHOWS

### Market Regime Info:
- ✅ Always shows (if data available)
- Shows: BULL 🟢 / CHOPPY 🟡 / BEAR 🔴
- Shows: Nifty level, 200 DMA, HOT sectors

### Weak Sector Warning:
- ✅ Only shows if market is CHOPPY or BEAR
- ✅ Only shows if you have open trades in weak sectors
- Lists up to 5 weak sector trades
- Shows sector name + current P&L

---

## 💡 WHAT TO DO WITH THIS INFO

### If Market is BULL 🟢:
- All sectors work
- No warnings shown
- Trade normally

### If Market is CHOPPY 🟡:
- Some sectors work (HOT sectors)
- Warning shows weak sector trades
- Consider:
  - Exit weak sector trades
  - Focus new trades on HOT sectors only

### If Market is BEAR 🔴:
- Few sectors work (HOT sectors only)
- Warning shows weak sector trades
- Recommended:
  - Exit ALL weak sector trades
  - Only hold HOT sector trades
  - Stop taking new trades (unless HOT sectors)

---

## 🚀 HOW TO USE

### Check Your Tracker:
```powershell
cd F:\projects\claude\scanner-v3
python paper_tracker.py status
```

**You'll see**:
1. Market regime (BULL/CHOPPY/BEAR)
2. HOT sectors list
3. Warning if you have weak sector trades
4. Full tracker status

### Daily Routine:
```powershell
# Morning: Check market regime
python paper_tracker.py status

# If BEAR market + weak sector trades:
# → Consider exiting those trades

# Evening: Update prices
python paper_tracker.py update
python paper_tracker.py status
```

---

## 📋 EXAMPLE SCENARIOS

### Scenario 1: BULL Market
```
MARKET: 🟢 BULL | Nifty: 25,500 | 200 DMA: 24,800
HOT Sectors: 🔥 Auto, Banking, IT, Pharma, FMCG, Metals

OPEN: 20 | CLOSED: 5 | TRADEABLE: 25

[No warnings - all sectors work]
```

### Scenario 2: CHOPPY Market
```
MARKET: 🟡 CHOPPY | Nifty: 24,800 | 200 DMA: 24,700
HOT Sectors: 🔥 Pharma, IT, FMCG

OPEN: 20 | CLOSED: 5 | TRADEABLE: 25

⚠️  WARNING: 8 open trades in WEAK sectors
Consider exiting these:
  - TATAMOTORS    (Auto        ) P&L: -2.10%
  - DLF           (Realty      ) P&L: -3.50%
  - RELIANCE      (Energy      ) P&L: -1.20%
  ... and 5 more
```

### Scenario 3: BEAR Market (Current)
```
MARKET: 🔴 BEAR | Nifty: 24,192 | 200 DMA: 24,677
HOT Sectors: 🔥 Pharma, IT, FMCG

OPEN: 73 | CLOSED: 13 | TRADEABLE: 230

⚠️  WARNING: 50 open trades in WEAK sectors
Consider exiting these:
  - RELIANCE      (Energy      ) P&L: -2.50%
  - TATAMOTORS    (Auto        ) P&L: -3.20%
  - DLF           (Realty      ) P&L: -1.80%
  - VEDL          (Metals      ) P&L: +5.53%
  - SAIL          (Metals      ) P&L: +3.59%
  ... and 45 more
```

---

## ⚠️ IMPORTANT NOTES

1. **Rate Limiting**: If yfinance is rate-limited, regime info won't show (this is normal)
2. **Sector Classification**: Uses same sector mapping as scanner (NSE official + yfinance)
3. **HOT Sectors**: Updates daily based on sector heat map (RISING/BOOM signals)
4. **Weak Sector Trades**: Doesn't mean exit immediately - use your judgment
5. **P&L Shown**: Current P&L for each weak sector trade (helps prioritize exits)

---

## 📝 SUMMARY

**What**: Paper tracker now shows market regime + warns about weak sector trades

**Why**: Helps you manage risk in weak markets

**When**: Shows every time you run `python paper_tracker.py status`

**Action**: Consider exiting weak sector trades in CHOPPY/BEAR markets

---

## ✅ FILES UPDATED

- `paper_tracker.py` - Added market regime display + weak sector warnings

**No breaking changes. All existing functionality works as before.** ✅
