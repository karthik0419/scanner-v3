"""
Entry confirmation filter — ported from scanner/ (v6) utils/entry_confirmation.py.

Simplified to use ONLY daily OHLCV data (no 4H, no weekly — v3.1 backtest
engine only has daily bars). 9 indicators, each returns 0-100 strength.

Total score = weighted average of all indicators.
If score >= threshold, trade is allowed. Otherwise rejected.

Indicators ported:
  1. Candlestick patterns (hammer, engulfing, strong bullish)
  2. Breakout confirmation (close above BO, sustained 2/3 days)
  3. Consolidation break (tight range break)
  4. Volume spike (1.5x avg)
  5. Volume accumulation (consistent high volume 5d)
  6. RSI confirmation (40-60 optimal, 30-70 ok)
  7. MACD signal (bullish crossover or above signal line)
  8. MA alignment (20MA > 50MA, price above 20MA)
  9. Price momentum (5d/10d positive)

Dropped (not portable / not useful for EOD backtest):
  - check_pullback_entry (conflicts with breakout strategy)
  - check_volume_divergence (too noisy)
  - check_4h_alignment (no 4H data in backtest)
  - check_weekly_alignment (v3.1 already has weekly patterns)
  - check_time_of_day (irrelevant for EOD backtest)
"""
import pandas as pd
import numpy as np


def _candlestick_patterns(df):
    """Bullish candlestick at entry bar."""
    if len(df) < 3:
        return 0
    last = df.iloc[-1]
    prev = df.iloc[-2]
    patterns = []
    # Hammer
    if (last['Close'] > prev['Close'] and
            (last['High'] - last['Low']) > 2 * abs(last['Open'] - last['Close'])):
        patterns.append("Hammer")
    # Bullish engulfing
    if (prev['Close'] < prev['Open'] and
            last['Close'] > last['Open'] and
            last['Close'] > prev['Open'] and
            last['Open'] < prev['Close']):
        patterns.append("Bullish Engulfing")
    # Strong bullish candle (>2% body)
    if (last['Close'] > last['Open'] and
            (last['Close'] - last['Open']) / last['Open'] > 0.02):
        patterns.append("Strong Bullish Candle")
    if patterns:
        return 80
    return 20


def _breakout_confirmation(df, breakout_level):
    """Close above breakout, sustained 2/3 days."""
    if len(df) < 5 or breakout_level <= 0:
        return 0
    current = df['Close'].iloc[-1]
    if current > breakout_level * 1.002:
        recent = df['Close'].tail(3)
        if sum(1 for c in recent if c > breakout_level) >= 2:
            return 90
        return 60
    return 10


def _consolidation_break(df):
    """Break from tight 10-bar range."""
    if len(df) < 15:
        return 0
    recent = df['Close'].tail(10)
    price_range = recent.max() - recent.min()
    avg = recent.mean()
    current = df['Close'].iloc[-1]
    if price_range / avg < 0.03 and current > recent.max() * 1.01:
        return 85
    return 25


def _volume_spike(df):
    """Volume > 1.5x avg."""
    if len(df) < 20:
        return 0
    cur_vol = df['Volume'].iloc[-1]
    avg_vol = df['Volume'].tail(20).mean()
    if cur_vol > avg_vol * 1.5:
        return 85
    elif cur_vol > avg_vol * 1.2:
        return 60
    return 20


def _volume_accumulation(df):
    """Consistent high volume over 5 days."""
    if len(df) < 20:
        return 0
    recent = df['Volume'].tail(5)
    avg_vol = df['Volume'].tail(20).mean()
    if all(v > avg_vol * 1.1 for v in recent):
        return 75
    elif sum(1 for v in recent if v > avg_vol) >= 3:
        return 50
    return 25


def _rsi_confirmation(df):
    """RSI in favorable range."""
    if len(df) < 14:
        return 0
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    if np.isnan(rsi):
        return 50
    if 40 <= rsi <= 60:
        return 80
    elif 30 <= rsi <= 70:
        return 60
    elif rsi > 70:
        return 30  # overbought
    return 30  # oversold


def _macd_signal(df):
    """MACD bullish crossover or above signal line."""
    if len(df) < 26:
        return 0
    exp1 = df['Close'].ewm(span=12).mean()
    exp2 = df['Close'].ewm(span=26).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9).mean()
    cur_macd = macd.iloc[-1]
    cur_sig = signal.iloc[-1]
    prev_macd = macd.iloc[-2]
    prev_sig = signal.iloc[-2]
    if prev_macd <= prev_sig and cur_macd > cur_sig:
        return 75  # bullish crossover
    elif cur_macd > cur_sig:
        return 50
    return 25


def _ma_alignment(df):
    """MA20 > MA50 and price above MA20."""
    if len(df) < 50:
        return 0
    ma20 = df['Close'].rolling(20).mean()
    ma50 = df['Close'].rolling(50).mean()
    cur_price = df['Close'].iloc[-1]
    cur_ma20 = ma20.iloc[-1]
    cur_ma50 = ma50.iloc[-1]
    prev_ma20 = ma20.iloc[-2]
    prev_ma50 = ma50.iloc[-2]
    if prev_ma20 <= prev_ma50 and cur_ma20 > cur_ma50:
        return 85  # golden cross
    elif cur_ma20 > cur_ma50 and cur_price > cur_ma20:
        return 60
    return 30


def _price_momentum(df):
    """5-day and 10-day positive momentum."""
    if len(df) < 11:
        return 0
    chg5 = (df['Close'].iloc[-1] - df['Close'].iloc[-6]) / df['Close'].iloc[-6]
    chg10 = (df['Close'].iloc[-1] - df['Close'].iloc[-11]) / df['Close'].iloc[-11]
    if chg5 > 0.02 and chg10 > 0.03:
        return 75
    elif chg5 > 0 or chg10 > 0:
        return 50
    return 25


# Weights (sum = 100) — mirrors v6's relative importance
WEIGHTS = {
    'candlestick':    10,
    'breakout_conf':  15,
    'consolidation':  10,
    'vol_spike':      12,
    'vol_accum':      10,
    'rsi':            10,
    'macd':           13,
    'ma_align':       12,
    'momentum':        8,
}


def score_entry(df, breakout_level):
    """Calculate entry confirmation score (0-100).

    Returns (score, details_dict).
    """
    if df is None or len(df) < 50:
        return 50, {}  # neutral if insufficient data

    indicators = {
        'candlestick':   _candlestick_patterns(df),
        'breakout_conf': _breakout_confirmation(df, breakout_level),
        'consolidation': _consolidation_break(df),
        'vol_spike':     _volume_spike(df),
        'vol_accum':     _volume_accumulation(df),
        'rsi':           _rsi_confirmation(df),
        'macd':          _macd_signal(df),
        'ma_align':      _ma_alignment(df),
        'momentum':      _price_momentum(df),
    }

    total = sum(indicators[k] * WEIGHTS[k] for k in WEIGHTS) / sum(WEIGHTS.values())
    return round(total, 1), indicators
