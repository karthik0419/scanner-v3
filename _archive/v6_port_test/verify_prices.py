"""Verify portfolio trade prices against current yfinance data."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import yfinance as yf
from datetime import datetime

# Load both portfolio CSVs
multi = pd.read_csv('results/portfolio_multi_20260803.csv')
allin = pd.read_csv('results/portfolio_allin_20260803.csv')

print(f"MULTI mode: {len(multi)} trades, {multi['symbol'].nunique()} unique stocks")
print(f"ALL-IN mode: {len(allin)} trades, {allin['symbol'].nunique()} unique stocks")
print()

# Get all unique stocks
all_stocks = sorted(set(multi['symbol'].unique()) | set(allin['symbol'].unique()))
print(f"Total unique stocks across both: {len(all_stocks)}")
print()

# For each stock, verify:
# 1. Stock still exists on yfinance (not delisted)
# 2. Entry/exit prices in our CSV match yfinance historical data
# 3. Current price for reference

results = []
verified = 0
mismatches = 0
delisted = 0

for i, sym in enumerate(all_stocks):
    stock_trades = multi[multi['symbol'] == sym]
    sample = stock_trades.iloc[0] if len(stock_trades) > 0 else allin[allin['symbol'] == sym].iloc[0]

    try:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="5d")
        if hist is None or len(hist) == 0:
            results.append({"symbol": sym, "status": "DELISTED", "current_price": None,
                            "trade_entry": sample['entry_price'], "trade_exit": sample['exit_price']})
            delisted += 1
            continue

        current_price = float(hist['Close'].iloc[-1])

        # Verify entry price against historical data
        entry_date = pd.to_datetime(sample['entry_date']).tz_localize(None)
        hist_full = ticker.history(period="6y")
        if hist_full.index.tz is not None:
            hist_full.index = hist_full.index.tz_localize(None)

        # Find the entry date in historical data
        entry_match = hist_full[hist_full.index == entry_date]
        if len(entry_match) > 0:
            actual_open = float(entry_match['Open'].iloc[0])
            actual_close = float(entry_match['Close'].iloc[0])
            # Our entry_price includes slippage (0.1%)
            expected_entry = actual_open * 1.001  # slippage
            diff_pct = abs(sample['entry_price'] - expected_entry) / expected_entry * 100

            if diff_pct < 0.5:  # within 0.5% is fine (slippage rounding)
                status = "VERIFIED"
                verified += 1
            else:
                status = f"MISMATCH ({diff_pct:.2f}%)"
                mismatches += 1
        else:
            status = "NO_HISTORY"
            mismatches += 1

        results.append({
            "symbol": sym,
            "status": status,
            "current_price": round(current_price, 2),
            "trade_entry": sample['entry_price'],
            "trade_exit": sample['exit_price'],
            "entry_date": sample['entry_date'],
        })

    except Exception as e:
        results.append({"symbol": sym, "status": f"ERROR: {str(e)[:30]}",
                        "current_price": None, "trade_entry": sample['entry_price'],
                        "trade_exit": sample['exit_price'], "entry_date": sample['entry_date']})
        delisted += 1

    if (i + 1) % 50 == 0:
        print(f"  ... {i+1}/{len(all_stocks)} verified ({verified} ok, {mismatches} mismatch, {delisted} delisted)")

# Results
print()
print("=" * 80)
print("  VERIFICATION RESULTS")
print("=" * 80)
print(f"  Total stocks:    {len(all_stocks)}")
print(f"  Verified OK:     {verified}")
print(f"  Mismatches:      {mismatches}")
print(f"  Delisted/Error:  {delisted}")
print()

rdf = pd.DataFrame(results)

# Show delisted/errored stocks
bad = rdf[rdf['status'].isin(['DELISTED', 'NO_HISTORY']) | rdf['status'].str.startswith('ERROR') | rdf['status'].str.startswith('MISMATCH')]
if len(bad) > 0:
    print("  STOCKS WITH ISSUES:")
    for _, r in bad.iterrows():
        print(f"    {r['symbol']:>16s}  status={r['status']:>20s}  trade_entry={r['trade_entry']}  current={r.get('current_price', 'N/A')}")
    print()

# Show current prices for all verified stocks
print("  CURRENT PRICES (verified stocks):")
print(f"    {'Symbol':>16s}  {'Current':>10s}  {'Last Entry':>10s}  {'Last Exit':>10s}  {'Entry Date':>12s}")
print(f"    {'-'*16}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*12}")
verified_stocks = rdf[rdf['status'] == 'VERIFIED'].sort_values('symbol')
for _, r in verified_stocks.iterrows():
    print(f"    {r['symbol']:>16s}  Rs {r['current_price']:>7.2f}  Rs {r['trade_entry']:>7.2f}  Rs {r['trade_exit']:>7.2f}  {r['entry_date']}")

# Save
out = os.path.join('results', f'price_verification_{datetime.now().strftime('%Y%m%d')}.csv')
rdf.to_csv(out, index=False)
print(f"\n  Saved: {out}")
