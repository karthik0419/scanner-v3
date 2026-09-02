import yfinance as yf
import pandas as pd

stocks = ['TILAKNAGAR.NS', 'JTL.NS']

for s in stocks:
    print(f'\n{s}:')
    try:
        data = yf.download(s, period='1y', progress=False)
        if not data.empty:
            print(f'  CMP: {data["Close"].iloc[-1]:.2f}')
            print(f'  52w High: {data["High"].max():.2f}')
            print(f'  52w Low: {data["Low"].min():.2f}')
            print(f'  Avg Volume: {data["Volume"].mean():.0f}')
            print(f'  Recent Volume: {data["Volume"].iloc[-1]:.0f}')
            vol_ratio = data["Volume"].iloc[-1] / data["Volume"].mean()
            print(f'  Volume Ratio: {vol_ratio:.2f}x')
        else:
            print('  No data')
    except Exception as e:
        print(f'  Error: {e}')
