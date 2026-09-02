"""
Backtest engine v3 + entry confirmation filter.

Same as backtester/engine.py but adds an optional entry_filter threshold.
When entry_filter > 0, each signal is scored by entry_filter.score_entry()
and only entered if score >= threshold.

This is a COPY for testing — the main project's engine.py is untouched.
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
from entry_filter import score_entry

MAX_HOLD_DAYS = 45

DETECTORS = [
    ("monthly_ch",  lambda df, dfw: detect_cup_handle_monthly(resample_monthly(df)), "Monthly"),
    ("weekly_ch",   lambda df, dfw: detect_cup_handle_weekly(dfw),                   "Weekly"),
    ("daily_ch",    lambda df, dfw: detect_cup_handle(df),                           "Daily"),
    ("double_bot",  lambda df, dfw: detect_double_bottom(df),                        "Daily"),
    ("desc_channel",lambda df, dfw: detect_descending_channel(df),                   "Daily"),
    ("asc_channel", lambda df, dfw: detect_ascending_channel(df),                    "Daily"),
    ("triangle",    lambda df, dfw: detect_triangle(df),                             "Daily"),
    ("darvas",      lambda df, dfw: detect_darvas_box(df),                           "Daily"),
    ("flag",        lambda df, dfw: detect_flag_pennant(df),                         "Daily"),
    ("wedge",       lambda df, dfw: detect_descending_wedge(df),                     "Daily"),
    ("sr",          lambda df, dfw: detect_sr_levels(df),                            "Daily"),
    ("break_retest",lambda df, dfw: detect_break_retest(df),                         "Daily"),
    ("retest",      lambda df, dfw: detect_retest(df),                               "Daily"),
    ("compression", lambda df, dfw: detect_compression(df),                          "Daily"),
    ("breakout",    lambda df, dfw: detect_breakout(df),                             "Daily"),
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
    for name, detect, timeframe in DETECTORS:
        try:
            result = detect(df_slice, df_weekly_slice)
            if result:
                result["timeframe"] = timeframe
                return result
        except Exception:
            continue
    return None


def _add_targets(result):
    breakout = result.get("breakout", 0)
    target2  = result.get("target", 0)
    if breakout > 0 and target2 > breakout:
        move = target2 - breakout
        result["target_1"] = round(breakout + move * 0.50, 2)
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

    entry = breakout if breakout > 0 and breakout <= cmp * 1.02 else cmp
    upside = (target - entry) / entry * 100
    risk   = (entry - stop) / entry * 100
    rr     = upside / risk if risk > 0 else 0

    if risk > 8:
        rr *= 0.5
    elif risk > 6:
        rr *= 0.8

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
    tf  = result.get("timeframe", "Daily")
    pat_tf = f"{pat} [{tf}]" if "Cup & Handle" in pat else pat
    pat_bonus = {
        "Cup & Handle [Monthly]":        30,
        "Cup & Handle [Weekly]":         28,
        "Cup & Handle":                  20,
        "Double Bottom":                 28,
        "Ascending Triangle":            15,
        "Symmetrical Triangle":          12,
        "Darvas Box":                    15,
        "Bullish Flag":                  12,
        "Descending Wedge":              8,
        "Break & Retest":                10,
        "S&R Breakout":                  14,
        "Channel Breakout (Descending)": 12,
        "Channel Breakout (Ascending)":  10,
        "Channel Breakout":              8,
        "S&R Support":                   22,
        "Resistance Breakout":           10,
    }
    score += pat_bonus.get(pat_tf, pat_bonus.get(pat, 5))
    normalised = round(min(score / 155 * 100, 100), 1)
    return normalised, round(rr, 2)


def _apply_atr_stop(result, df_slice, atr_multiplier=None):
    pat = result.get("pattern", "")
    cmp = result.get("cmp", 0)
    current_stop = result.get("stop_loss", 0)
    current_risk = (cmp - current_stop) / cmp if cmp else 0
    MAX_RISK = 0.08

    if current_risk <= MAX_RISK:
        return result

    if atr_multiplier is None:
        atr_multiplier = 2.0

    atr = _calc_atr(df_slice, period=14)
    breakout = result.get("breakout", 0)

    if atr > 0:
        new_stop = round(breakout - (atr_multiplier * atr), 2)
        if new_stop > 0 and new_stop < cmp:
            max_stop_drop = cmp * (1 - MAX_RISK)
            new_stop = max(new_stop, max_stop_drop)
            new_risk = (cmp - new_stop) / cmp
            if new_risk <= MAX_RISK:
                result["stop_loss"] = new_stop
                result["atr"] = round(atr, 2)
                result["atr_mult"] = atr_multiplier
                result["stop_tightened"] = True
                return result

    result["stop_loss"] = round(cmp * (1 - MAX_RISK), 2)
    result["stop_capped"] = True
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


def _data_is_sane(df, symbol=""):
    if df is None or len(df) < 2:
        return False
    pct = df["Close"].pct_change().abs()
    bad_days = pct[pct > 0.40]
    if len(bad_days) > 0:
        return False
    return True


def backtest_symbol(symbol, years=2, min_score=50, scan_every=5,
                    atr_stop=True, entry_filter_threshold=0):
    """Walk-forward backtest with optional entry confirmation filter.

    entry_filter_threshold: 0 = disabled (baseline). >0 = min confirmation score required.
    """
    df = _fetch_nse(symbol.replace(".NS", ""), days=years * 365)
    if df is None or len(df) < 140 + 10:
        return []
    if not _data_is_sane(df, symbol):
        return []

    trades = []
    open_trade = None
    last_scan_idx = 0
    t1_hit = False
    trailing_stop = None
    last_breakout = 0
    last_sl_date = None
    RE_ENTRY_COOLDOWN = 10
    RE_ENTRY_MAX_DAYS = 30

    for i in range(140, len(df)):
        current_date = df.index[i]
        row = df.iloc[i]
        low = float(row["Low"])
        high = float(row["High"])
        close = float(row["Close"])

        # --- Re-entry after whipsaw ---
        if (open_trade is None and last_breakout > 0 and last_sl_date is not None
                and (i - last_scan_idx) >= 1):
            days_since_sl = (current_date - last_sl_date).days
            if days_since_sl <= RE_ENTRY_MAX_DAYS and close >= last_breakout:
                if i + 1 < len(df):
                    re_entry_price = float(df.iloc[i + 1]["Open"])
                    re_entry_stop = round(last_breakout * 0.98, 2)
                    if re_entry_stop < re_entry_price:
                        open_trade = {
                            "symbol": symbol,
                            "pattern": "Re-entry",
                            "signal_date": current_date,
                            "entry_date": df.index[i + 1],
                            "entry_price": re_entry_price,
                            "stop_loss": re_entry_stop,
                            "target_1": round(last_breakout + (last_breakout - re_entry_stop) * 2, 2),
                            "target_2": round(last_breakout + (last_breakout - re_entry_stop) * 3, 2),
                            "score": 50, "rr": 2.0, "status": "RE_ENTRY",
                            "atr": 0, "exit_price": None, "exit_date": None,
                            "exit_reason": None, "pnl_pct": None, "result": None,
                            "days_held": None, "quantity_pct": 100,
                            "breakout_level": last_breakout,
                            "entry_conf_score": -1,  # re-entries skip filter
                        }
                        last_breakout = 0
                        last_sl_date = None
                        last_scan_idx = i
                        continue

        # --- Manage open trade ---
        if open_trade is not None:
            entry_price = open_trade["entry_price"]
            days_held = (current_date - open_trade["entry_date"]).days

            effective_stop = trailing_stop if t1_hit else open_trade["stop_loss"]
            if low <= effective_stop:
                trades.append(_close_trade(open_trade, effective_stop, current_date,
                                           "Trailing Stop" if t1_hit else "Stop Loss"))
                last_breakout = open_trade.get("breakout_level", 0)
                last_sl_date = current_date
                open_trade = None
                t1_hit = False
                trailing_stop = None
                continue

            if high >= open_trade["target_2"]:
                trades.append(_close_trade(open_trade, open_trade["target_2"], current_date, "Target 2"))
                open_trade = None
                t1_hit = False
                trailing_stop = None
                last_breakout = 0
                continue

            if not t1_hit and high >= open_trade["target_1"]:
                t1_trade = dict(open_trade)
                t1_trade["quantity_pct"] = 50
                trades.append(_close_trade(t1_trade, open_trade["target_1"], current_date, "Target 1"))
                t1_hit = True
                trailing_stop = entry_price
                continue

            if days_held >= MAX_HOLD_DAYS:
                trades.append(_close_trade(open_trade, close, current_date, "Time Exit"))
                open_trade = None
                t1_hit = False
                trailing_stop = None
                last_breakout = 0
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

                cmp_val = result.get("cmp", 0)
                stop_val = result.get("stop_loss", 0)
                bo_val = result.get("breakout", 0)
                risk_pct = (cmp_val - stop_val) / cmp_val * 100 if cmp_val else 0
                if risk_pct > 10:
                    continue
                dist_pct = abs(bo_val - cmp_val) / cmp_val * 100 if bo_val and cmp_val else 0
                if bo_val > 0 and dist_pct > 8 and result.get("status") != "BREAKOUT":
                    continue

                if score >= min_score and rr > 0:
                    # --- ENTRY CONFIRMATION FILTER ---
                    conf_score = -1
                    if entry_filter_threshold > 0:
                        conf_score, _ = score_entry(df_slice, bo_val)
                        if conf_score < entry_filter_threshold:
                            continue  # rejected by entry filter

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
                        "quantity_pct": 100,
                        "breakout_level": result.get("breakout", 0),
                        "entry_conf_score": conf_score,
                    }

    if open_trade is not None:
        last_close = float(df.iloc[-1]["Close"])
        last_date = df.index[-1]
        trades.append(_close_trade(open_trade, last_close, last_date, "End of Data"))

    return trades


def backtest_portfolio(symbols, years=2, min_score=50, scan_every=5,
                       atr_stop=True, entry_filter_threshold=0):
    """Run backtest across a list of symbols and return all trades."""
    all_trades = []
    total = len(symbols)
    for idx, sym in enumerate(symbols):
        print(f"  [{idx+1}/{total}] Backtesting {sym:<20}", end=" ", flush=True)
        trades = backtest_symbol(sym, years=years, min_score=min_score,
                                 scan_every=scan_every, atr_stop=atr_stop,
                                 entry_filter_threshold=entry_filter_threshold)
        print(f"{len(trades)} trades")
        all_trades.extend(trades)
    return all_trades
