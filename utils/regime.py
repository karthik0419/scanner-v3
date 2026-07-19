"""
Market Regime Filter — Nifty 50 vs its 200-day moving average.

Motivation: 5-year backtest (2021-2026) showed v3 expectancy is regime-dependent:
  2023: +6.93%  |  2024: +3.66%  |  2025: -0.35% (losing year)
Long setups underperform when the broad market is below its long-term trend.

Usage:
    from utils.regime import get_market_regime
    regime = get_market_regime()   # dict with status, close, dma200, pct_from_dma
"""
import yfinance as yf


def get_market_regime(symbol="^NSEI"):
    """
    Returns dict:
      status: "RISK_ON" (Nifty above 200DMA) or "RISK_OFF" (below)
      close: latest close
      dma200: 200-day moving average
      pct_from_dma: % distance of close from the 200DMA
    Returns None if data unavailable (fail open — scanner proceeds).
    """
    try:
        df = yf.Ticker(symbol).history(period="1y")
        if df is None or len(df) < 200:
            return None
        close = float(df["Close"].iloc[-1])
        dma200 = float(df["Close"].rolling(200).mean().iloc[-1])
        pct = (close - dma200) / dma200 * 100
        return {
            "status": "RISK_ON" if close > dma200 else "RISK_OFF",
            "close": close,
            "dma200": dma200,
            "pct_from_dma": pct,
        }
    except Exception:
        return None


def print_regime_banner(regime, bearish=False):
    """Print a prominent regime banner. Warns when scan direction fights the regime."""
    if regime is None:
        print("  REGIME: unavailable (index data fetch failed) — proceeding")
        return
    status = regime["status"]
    print(f"  REGIME: {status} | Nifty {regime['close']:.0f} vs 200DMA "
          f"{regime['dma200']:.0f} ({regime['pct_from_dma']:+.1f}%)")
    if status == "RISK_OFF" and not bearish:
        print("  " + "!" * 60)
        print("  !! Nifty BELOW 200DMA — long setups historically lose money")
        print("  !! in this regime (2025 backtest: -0.35%/trade).")
        print("  !! Reduce position size or trade the --bearish scan instead.")
        print("  " + "!" * 60)
    elif status == "RISK_ON" and bearish:
        print("  NOTE: Nifty above 200DMA — shorts fight the broad uptrend.")
