"""Fetch TECHM current price and recent data."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.loader import _fetch_nse
import pandas as pd

df = _fetch_nse('TECHM', days=30)
if df is not None and not df.empty:
    cur = float(df['Close'].iloc[-1])
    print(f"Current price: {cur:.2f}")
    print()
    print("Recent 10 days:")
    for i in range(-10, 0):
        print(f"  {df.index[i].date()}  O={df['Open'].iloc[i]:.2f}  H={df['High'].iloc[i]:.2f}  L={df['Low'].iloc[i]:.2f}  C={df['Close'].iloc[i]:.2f}  V={df['Volume'].iloc[i]:.0f}")

    # Calculate ATR
    import numpy as np
    tr = np.maximum(df['High'] - df['Low'],
                    np.maximum((df['High'] - df['Close'].shift(1)).abs(),
                               (df['Low'] - df['Close'].shift(1)).abs()))
    atr = tr.rolling(14).mean().iloc[-1]
    print(f"\nATR(14): {atr:.2f}")

    # Support/resistance
    high_50 = df['High'].tail(50).max()
    low_50 = df['Low'].tail(50).min()
    print(f"50-day high: {high_50:.2f}")
    print(f"50-day low: {low_50:.2f}")

    # SMA
    sma_20 = df['Close'].rolling(20).mean().iloc[-1]
    sma_50 = df['Close'].rolling(50).mean().iloc[-1]
    print(f"SMA20: {sma_20:.2f}")
    print(f"SMA50: {sma_50:.2f}")
else:
    print("No data for TECHM")
