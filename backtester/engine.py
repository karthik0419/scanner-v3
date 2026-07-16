"""
Backtest engine v3 — walk-forward backtester for scanner-v3 patterns.

Key differences vs scanner/backtester/engine.py:
  - Uses ALL v3 pattern detectors (not just a subset)
  - ATR-based stop loss (matching v3's default sl_mode)
  - T1/T2 targets (matching v3's two-target system)
  - Trailing stop after T1 hit (v3 improvement — T2 rarely reached)
  - Sector rotation bonus included in scoring

Entry rule: next bar's open after signal detection (no lookahead).
Exit rules (checked in priority order each bar):
  1. Low <= stop_loss        -> exit at stop_loss
  2. High >= target_2         -> exit at target_2 (full target)
  3. High >= target_1         -> exit at target_1, then trail stop to breakeven
  4. Low <= trailing_stop     -> exit at trailing_stop (after T1 hit)
  5. days_held >= MAX_HOLD    -> exit at close
"""
import os, sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.loader import _fetch_nse, _resample_weekly
from patterns.cup_handle import detect_cup_handle, detect_cup_handle_weekly
from patterns.cup_handle_monthly import detect_cup_handle_monthly, resample_monthly
from patterns.double_bottom import detect_double_bottom
from patterns.wedge import detect_descending_wedge
from patterns.breakout import detect_breakout
from patterns.break_retest import detect_break_retest
from patterns.channel import detect_descending_channel, detect_ascending_channel
from patterns.triangle import detect_triangle
from patterns.darvas_box import detect_darvas_box
from patterns.flags import detect_flag_pennant
from patterns.sr_levels import detect_sr_levels
from patterns.retest import detect_retest
from patterns.compression import detect_compression

MAX_HOLD_DAYS = 45  # v3: increased from 30 to 45 (swing trades need more room)


# Pattern priority — matches scanner.py _detect_pattern
DETECTORS = [
    ("monthly_ch",  lambda df, dfw: detect_cup_handle_monthly(resample_monthly(df))),
    ("weekly_ch",   lambda df, dfw: detect_cup_handle_weekly(dfw)),
    ("daily_ch",    lambda df, dfw: detect_cup_handle(df)),
    ("double_bot",  lambda df, dfw: detect_double_bottom(df)),
    ("desc_channel",lambda df, dfw: detect_descending_channel(df)),
    ("asc_channel", lambda df, dfw: detect_ascending_channel(df)),
    ("triangle",    lambda df, dfw: detect_triangle(df)),
    ("darvas",      lambda df, dfw: detect_darvas_box(df)),
    ("flag",        lambda df, dfw: detect_flag_pennant(df)),
    ("wedge",       lambda df, dfw: detect_descending_wedge(df)),
    ("sr",          lambda df, dfw: detect_sr_levels(df)),
    ("break_retest",lambda df, dfw: detect_break_retest(df)),
    ("retest",      lambda df, dfw: detect_retest(df)),
    ("compression", lambda df, dfw: detect_compression(df)),
    ("breakout",    lambda df, dfw: detect_breakout(df)),
]


def _calc_atr(df, period=14):
    if df is None or len(df) < period + 1:
        return 0
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    tr = np.zeros(len(df))
    for i in range(1, len(df)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    return float(np.mean(tr[-period:]))


def _detect_signal(df_slice, df_weekly_slice):
    for name, detect in DETECTORS:
        try:
            result = detect(df_slice, df_weekly_slice)
            if result:
                return result
        except Exception:
            continue
    return None


def _add_targets(result):
    breakout = result.get("breakout", 0)
    target2  = result.get("target", 0)
    if breakout > 0 and target2 > breakout:
        move = target2 - breakout
        result["target_1"] = round(breakout + move * 0.60, 2)
        result["target_2"] = round(target2, 2)
    else:
        result["target_1"] = result.get("target", 0)
        result["target_2"] = result.get("target", 0)
    return result


def _score(result):
    cmp      = result.get("cmp", 0)
    target   = result.get("target_1", result.get("target", 0))
    stop     = result.get("stop_loss", 0)
    breakout = result.get("breakout", 0)

    if cmp <= 0 or stop <= 0 or stop >= cmp:
        return 0, 0

    upside = (target - cmp) / cmp * 100
    risk   = (cmp - stop) / cmp * 100
    rr     = upside / risk if risk > 0 else 0

    score = 0
    if rr >= 3:   score += 40
    elif rr >= 2: score += 30
    elif rr >= 1: score += 15

    if result.get("volume"):  score += 20
    status = result.get("status", "")
    if status == "BREAKOUT": score += 25
    elif status == "NEAR":   score += 12
    elif status == "WATCH":  score += 5

    dist = abs(cmp - breakout) / breakout if breakout else 1
    if dist < 0.02:   score += 20
    elif dist < 0.05: score += 12
    elif dist < 0.10: score += 6

    pat = result.get("pattern", "")
    pat_bonus = {
        "Cup & Handle (Monthly)":        30,
        "Cup & Handle (Weekly)":         28,
        "Cup & Handle":                  20,
        "Double Bottom":                 28,
        "Ascending Triangle":            15,
        "Symmetrical Triangle":          12,
        "Darvas Box":                    15,
        "Bullish Flag":                  12,
        "Descending Wedge":              14,
        "Break & Retest":                10,
        "S&R Breakout":                  10,
        "Channel Breakout (Descending)": 12,
        "Channel Breakout (Ascending)":  10,
        "Channel Breakout":              8,
        "S&R Support":                   10,
        "Resistance Breakout":           10,
    }
    score += pat_bonus.get(pat, 5)
    normalised = round(min(score / 155 * 100, 100), 1)
    return normalised, round(rr, 2)


def _apply_atr_stop(result, df_slice, atr_multiplier=None):
    """Apply ATR-based stop loss with pattern-specific logic.

    Key finding from backtest: C&H and Wedge patterns have structurally
    meaningful stops (handle low, wedge low) that outperform ATR stops.
    ATR stops work better for patterns without structural stops (S&R, Breakout).

    Strategy: Keep original stops for C&H/Wedge, use ATR for everything else.
    """
    pat = result.get("pattern", "")

    # Patterns that should keep their original structural stop
    # (ATR stops reduced their win rate significantly in backtesting)
    KEEP_ORIGINAL_STOP = {
        "Cup & Handle":             True,   # handle low is structural — 48.9% WR vs 34.1% with ATR
        "Cup & Handle (Weekly)":    True,
        "Cup & Handle (Monthly)":   True,
        "Descending Wedge":         True,   # wedge low is structural — 28.6% WR vs 23.0% with ATR
        "Double Bottom":            False,  # ATR works fine — 56.6% WR
    }

    if KEEP_ORIGINAL_STOP.get(pat, False):
        # Keep the pattern's original stop loss (don't override with ATR)
        return result

    # Use ATR stop for patterns without structural stops
    if atr_multiplier is None:
        atr_multiplier = 1.5

    atr = _calc_atr(df_slice, period=14)
    if atr <= 0:
        return result
    breakout = result.get("breakout", 0)
    cmp = result.get("cmp", 0)
    new_stop = round(breakout - (atr_multiplier * atr), 2)
    if new_stop > 0 and new_stop < cmp:
        max_stop_drop = cmp * 0.92  # max 8% stop
        new_stop = max(new_stop, max_stop_drop)
        result["stop_loss"] = new_stop
        result["atr"] = round(atr, 2)
        result["atr_mult"] = atr_multiplier
    return result


def _close_trade(trade, exit_price, exit_date, exit_reason):
    trade["exit_price"] = round(exit_price, 2)
    trade["exit_date"] = exit_date
    trade["exit_reason"] = exit_reason
    trade["pnl_pct"] = round(
        (exit_price - trade["entry_price"]) / trade["entry_price"] * 100, 2
    )
    trade["result"] = "WIN" if trade["pnl_pct"] > 0 else "LOSS"
    trade["days_held"] = (exit_date - trade["entry_date"]).days
    return trade


def backtest_symbol(symbol, years=2, min_score=50, scan_every=5, atr_stop=True):
    """
    Walk-forward backtest for a single symbol using v3 patterns + ATR stops.
    """
    df = _fetch_nse(symbol.replace(".NS", ""), days=years * 365)
    if df is None or len(df) < 140 + 10:
        return []

    trades = []
    open_trade = None
    last_scan_idx = 0
    t1_hit = False
    trailing_stop = None

    for i in range(140, len(df)):
        current_date = df.index[i]
        row = df.iloc[i]
        low = float(row["Low"])
        high = float(row["High"])
        close = float(row["Close"])

        # --- Manage open trade ---
        if open_trade is not None:
            entry_price = open_trade["entry_price"]
            days_held = (current_date - open_trade["entry_date"]).days

            # 1. Stop loss hit
            effective_stop = trailing_stop if t1_hit else open_trade["stop_loss"]
            if low <= effective_stop:
                trades.append(_close_trade(open_trade, effective_stop, current_date,
                                           "Trailing Stop" if t1_hit else "Stop Loss"))
                open_trade = None
                t1_hit = False
                trailing_stop = None
                continue

            # 2. Target 2 hit (full target)
            if high >= open_trade["target_2"]:
                trades.append(_close_trade(open_trade, open_trade["target_2"], current_date, "Target 2"))
                open_trade = None
                t1_hit = False
                trailing_stop = None
                continue

            # 3. Target 1 hit — exit at T1, then set trailing stop for remaining position
            if not t1_hit and high >= open_trade["target_1"]:
                # Close half at T1 (simulate by recording T1 as a trade)
                t1_trade = dict(open_trade)
                t1_trade["quantity_pct"] = 50  # 50% closed at T1
                trades.append(_close_trade(t1_trade, open_trade["target_1"], current_date, "Target 1"))
                # Set trailing stop at breakeven (entry price) for remaining 50%
                t1_hit = True
                trailing_stop = entry_price  # breakeven stop
                continue

            # 4. Time exit
            if days_held >= MAX_HOLD_DAYS:
                trades.append(_close_trade(open_trade, close, current_date, "Time Exit"))
                open_trade = None
                t1_hit = False
                trailing_stop = None
                continue

        # --- Scan for new signal ---
        if open_trade is None and (i - last_scan_idx) >= scan_every:
            last_scan_idx = i
            df_slice = df.iloc[: i + 1].copy()
            df_weekly_slice = _resample_weekly(df_slice)

            result = _detect_signal(df_slice, df_weekly_slice)
            if result:
                result = _add_targets(result)
                if atr_stop:
                    result = _apply_atr_stop(result, df_slice)
                score, rr = _score(result)
                result["score"] = score
                result["rr"] = rr

                if score >= min_score and rr > 0:
                    if i + 1 >= len(df):
                        continue
                    entry_price = float(df.iloc[i + 1]["Open"])
                    stop_loss = result["stop_loss"]

                    if stop_loss >= entry_price:
                        continue

                    open_trade = {
                        "symbol": symbol,
                        "pattern": result["pattern"],
                        "signal_date": current_date,
                        "entry_date": df.index[i + 1],
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target_1": result["target_1"],
                        "target_2": result["target_2"],
                        "score": score,
                        "rr": rr,
                        "status": result.get("status", ""),
                        "atr": result.get("atr", 0),
                        "exit_price": None,
                        "exit_date": None,
                        "exit_reason": None,
                        "pnl_pct": None,
                        "result": None,
                        "days_held": None,
                        "quantity_pct": 100,  # full position unless T1 split
                    }

    # Close any remaining open trade
    if open_trade is not None:
        last_close = float(df.iloc[-1]["Close"])
        last_date = df.index[-1]
        trades.append(_close_trade(open_trade, last_close, last_date, "End of Data"))

    return trades


def backtest_portfolio(symbols, years=2, min_score=50, scan_every=5, atr_stop=True):
    """Run backtest across a list of symbols and return all trades."""
    all_trades = []
    total = len(symbols)
    for idx, sym in enumerate(symbols):
        print(f"  [{idx+1}/{total}] Backtesting {sym:<20}", end=" ", flush=True)
        trades = backtest_symbol(sym, years=years, min_score=min_score,
                                 scan_every=scan_every, atr_stop=atr_stop)
        print(f"{len(trades)} trades")
        all_trades.extend(trades)
    return all_trades
