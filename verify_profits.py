import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Stocks from your charts
stocks = {
    'EPL.NS': {'chart_date': '2026-08-22', 'chart_price': 265.61, 'target': 370},
    'ANTHEM.NS': {'chart_date': '2026-08-22', 'chart_price': 724.20, 'target': 850},
    'BALRAMCHIN.NS': {'chart_date': '2026-08-22', 'chart_price': 735.05, 'target': 900},
    'MANALIPETC.NS': {'chart_date': '2026-08-22', 'chart_price': 74.02, 'target': 106},
    'CHENNPETRO.NS': {'chart_date': '2026-08-22', 'chart_price': 1041.85, 'target': 1400},
    'BALUFORGE.NS': {'chart_date': '2026-08-22', 'chart_price': 555.40, 'target': 1080},
    'VARROC.NS': {'chart_date': '2026-08-22', 'chart_price': 679.20, 'target': 1000},
    'BRIGADE.NS': {'chart_date': '2026-08-22', 'chart_price': 625.75, 'target': 1200},
    'CONCORDBIO.NS': {'chart_date': '2026-08-22', 'chart_price': 1565.70, 'target': 2800},
    'ACE.NS': {'chart_date': '2026-08-22', 'chart_price': 1172.60, 'target': 1500},
    'JTLIND.NS': {'chart_date': '2026-08-22', 'chart_price': 79.52, 'target': 120},
    'TILAKNAGAR.NS': {'chart_date': '2026-08-22', 'chart_price': 584.15, 'target': 650},
}

print("=" * 100)
print("PROFIT VERIFICATION: Your Chart Stocks (Aug 22 to Aug 23)")
print("=" * 100)
print()

results = []

for symbol, info in stocks.items():
    try:
        # Fetch recent data
        data = yf.download(symbol, start='2026-08-20', end='2026-08-24', progress=False)
        
        if len(data) > 0:
            chart_price = info['chart_price']
            current_price = data['Close'].iloc[-1]
            if hasattr(current_price, 'values'):
                current_price = current_price.values[0]
            current_price = float(current_price)
            target = info['target']
            
            # Calculate profit
            profit_pct = ((current_price - chart_price) / chart_price) * 100
            target_pct = ((target - chart_price) / chart_price) * 100
            progress_pct = (profit_pct / target_pct) * 100 if target_pct > 0 else 0
            
            status = "PROFIT" if profit_pct > 0 else "LOSS" if profit_pct < 0 else "FLAT"
            
            results.append({
                'symbol': symbol.replace('.NS', ''),
                'chart_price': chart_price,
                'current': current_price,
                'profit_%': profit_pct,
                'target': target,
                'progress_%': progress_pct,
                'status': status
            })
            
            print(f"{symbol.replace('.NS', ''):15} | Chart: Rs{chart_price:8.2f} -> Now: Rs{current_price:8.2f} | {status:10} | {profit_pct:+6.2f}% | Target: Rs{target:.0f} ({progress_pct:.1f}% done)")
        else:
            print(f"{symbol.replace('.NS', ''):15} | NO DATA")
            
    except Exception as e:
        print(f"{symbol.replace('.NS', ''):15} | ERROR: {e}")

print()
print("=" * 100)
print("SUMMARY")
print("=" * 100)

if results:
    df = pd.DataFrame(results)
    
    winners = df[df['profit_%'] > 0]
    losers = df[df['profit_%'] < 0]
    flat = df[df['profit_%'] == 0]
    
    print(f"Total stocks: {len(df)}")
    print(f"Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")
    print(f"Flat: {len(flat)} ({len(flat)/len(df)*100:.1f}%)")
    print()
    print(f"Avg profit: {df['profit_%'].mean():+.2f}%")
    print(f"Best: {df.loc[df['profit_%'].idxmax(), 'symbol']} ({df['profit_%'].max():+.2f}%)")
    print(f"Worst: {df.loc[df['profit_%'].idmin(), 'symbol']} ({df['profit_%'].min():+.2f}%)")
    print()
    
    # Check scanner's rejected/WATCH stocks
    print("SCANNER'S REJECTED/WATCH STOCKS PERFORMANCE:")
    print("-" * 100)
    rejected = ['JTLIND', 'TILAKNAGAR']
    watch = ['CHENNPETRO', 'MANALIPETC']
    
    for stock in rejected + watch:
        row = df[df['symbol'] == stock]
        if not row.empty:
            profit = row['profit_%'].values[0]
            status = "REJECTED" if stock in rejected else "WATCH"
            print(f"  {stock:15} ({status:8}): {profit:+6.2f}%")
