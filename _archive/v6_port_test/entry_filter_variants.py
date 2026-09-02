"""
Entry filter variants for testing.

v1 = original (from v6 port) — RSI penalizes >70 as overbought
v2 = RSI overbought is NEUTRAL not penalty (breakout stocks often have RSI 70+)
v3 = volume + momentum only (drop RSI, MA, MACD — they conflict with breakouts)
v4 = adjusted weights — less RSI weight, more volume+momentum
v5 = RSI as BONUS for high values in breakouts (momentum confirmation)
v6 = hybrid — volume required (>=1.2x), momentum positive, RSI neutral
"""
import pandas as pd
import numpy as np


# ============ INDIVIDUAL INDICATORS (shared) ============

def _candlestick_patterns(df):
    if len(df) < 3:
        return 0
    last = df.iloc[-1]
    prev = df.iloc[-2]
    patterns = []
    if (last['Close'] > prev['Close'] and
            (last['High'] - last['Low']) > 2 * abs(last['Open'] - last['Close'])):
        patterns.append("Hammer")
    if (prev['Close'] < prev['Open'] and
            last['Close'] > last['Open'] and
            last['Close'] > prev['Open'] and
            last['Open'] < prev['Close']):
        patterns.append("Bullish Engulfing")
    if (last['Close'] > last['Open'] and
            (last['Close'] - last['Open']) / last['Open'] > 0.02):
        patterns.append("Strong Bullish Candle")
    if patterns:
        return 80
    return 20


def _breakout_confirmation(df, breakout_level):
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
    if len(df) < 20:
        return 0
    recent = df['Volume'].tail(5)
    avg_vol = df['Volume'].tail(20).mean()
    if all(v > avg_vol * 1.1 for v in recent):
        return 75
    elif sum(1 for v in recent if v > avg_vol) >= 3:
        return 50
    return 25


def _rsi_neutral(df):
    """RSI — no overbought penalty. 40-70 = good, anything else = neutral."""
    if len(df) < 14:
        return 50
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    if np.isnan(rsi):
        return 50
    if 40 <= rsi <= 70:
        return 70
    elif 30 <= rsi <= 80:
        return 55  # don't penalize 70-80 (breakout momentum)
    return 40  # only penalize extreme oversold (<30)


def _rsi_original(df):
    """Original v6 RSI — penalizes >70."""
    if len(df) < 14:
        return 50
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
        return 30  # overbought penalty
    return 30


def _rsi_momentum(df):
    """RSI as momentum bonus — high RSI (60-80) is GOOD for breakouts."""
    if len(df) < 14:
        return 50
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    if np.isnan(rsi):
        return 50
    if 60 <= rsi <= 80:
        return 80  # momentum zone — GOOD for breakouts
    elif 50 <= rsi <= 85:
        return 65
    elif 40 <= rsi <= 60:
        return 55
    elif rsi > 85:
        return 40  # only extreme overbought is bad
    return 35  # oversold


def _macd_signal(df):
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
        return 75
    elif cur_macd > cur_sig:
        return 50
    return 25


def _ma_alignment(df):
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
        return 85
    elif cur_ma20 > cur_ma50 and cur_price > cur_ma20:
        return 60
    return 30


def _price_momentum(df):
    if len(df) < 11:
        return 0
    chg5 = (df['Close'].iloc[-1] - df['Close'].iloc[-6]) / df['Close'].iloc[-6]
    chg10 = (df['Close'].iloc[-1] - df['Close'].iloc[-11]) / df['Close'].iloc[-11]
    if chg5 > 0.02 and chg10 > 0.03:
        return 75
    elif chg5 > 0 or chg10 > 0:
        return 50
    return 25


# ============ VARIANT DEFINITIONS ============

VARIANTS = {
    'v1_original': {
        'desc': 'Original v6 port — RSI penalizes >70',
        'indicators': {
            'candlestick':   (_candlestick_patterns, 10),
            'breakout_conf': (_breakout_confirmation, 15),
            'consolidation': (_consolidation_break, 10),
            'vol_spike':     (_volume_spike, 12),
            'vol_accum':     (_volume_accumulation, 10),
            'rsi':           (_rsi_original, 10),
            'macd':          (_macd_signal, 13),
            'ma_align':      (_ma_alignment, 12),
            'momentum':      (_price_momentum, 8),
        },
    },
    'v2_rsi_neutral': {
        'desc': 'RSI overbought = neutral (not penalty). Breakouts can have RSI 70+',
        'indicators': {
            'candlestick':   (_candlestick_patterns, 10),
            'breakout_conf': (_breakout_confirmation, 15),
            'consolidation': (_consolidation_break, 10),
            'vol_spike':     (_volume_spike, 12),
            'vol_accum':     (_volume_accumulation, 10),
            'rsi':           (_rsi_neutral, 10),
            'macd':          (_macd_signal, 13),
            'ma_align':      (_ma_alignment, 12),
            'momentum':      (_price_momentum, 8),
        },
    },
    'v3_vol_mom_only': {
        'desc': 'Volume + momentum only (drop RSI, MA, MACD — they conflict with breakouts)',
        'indicators': {
            'candlestick':   (_candlestick_patterns, 15),
            'breakout_conf': (_breakout_confirmation, 20),
            'consolidation': (_consolidation_break, 10),
            'vol_spike':     (_volume_spike, 20),
            'vol_accum':     (_volume_accumulation, 15),
            'momentum':      (_price_momentum, 20),
        },
    },
    'v4_less_rsi': {
        'desc': 'Adjusted weights — less RSI (5%), more volume (17%) + momentum (12%)',
        'indicators': {
            'candlestick':   (_candlestick_patterns, 10),
            'breakout_conf': (_breakout_confirmation, 15),
            'consolidation': (_consolidation_break, 10),
            'vol_spike':     (_volume_spike, 17),
            'vol_accum':     (_volume_accumulation, 12),
            'rsi':           (_rsi_neutral, 5),
            'macd':          (_macd_signal, 10),
            'ma_align':      (_ma_alignment, 9),
            'momentum':      (_price_momentum, 12),
        },
    },
    'v5_rsi_momentum': {
        'desc': 'RSI as momentum bonus — high RSI (60-80) is GOOD for breakouts',
        'indicators': {
            'candlestick':   (_candlestick_patterns, 10),
            'breakout_conf': (_breakout_confirmation, 15),
            'consolidation': (_consolidation_break, 10),
            'vol_spike':     (_volume_spike, 12),
            'vol_accum':     (_volume_accumulation, 10),
            'rsi':           (_rsi_momentum, 10),
            'macd':          (_macd_signal, 13),
            'ma_align':      (_ma_alignment, 12),
            'momentum':      (_price_momentum, 8),
        },
    },
    'v6_hybrid': {
        'desc': 'Hybrid — volume required + momentum positive + RSI neutral + breakout conf',
        'indicators': {
            'breakout_conf': (_breakout_confirmation, 25),
            'vol_spike':     (_volume_spike, 25),
            'vol_accum':     (_volume_accumulation, 15),
            'rsi':           (_rsi_neutral, 10),
            'momentum':      (_price_momentum, 25),
        },
    },
}


def score_entry(df, breakout_level, variant='v1_original'):
    """Calculate entry confirmation score (0-100) for given variant."""
    if df is None or len(df) < 50:
        return 50, {}

    config = VARIANTS[variant]
    indicators = {}
    for key, (func, weight) in config['indicators'].items():
        if key in ('breakout_conf',):
            indicators[key] = func(df, breakout_level)
        else:
            indicators[key] = func(df)

    total_weight = sum(w for _, w in config['indicators'].values())
    total = sum(indicators[k] * w for k, w in [(k, config['indicators'][k][1]) for k in indicators])
    score = total / total_weight if total_weight > 0 else 50
    return round(score, 1), indicators
