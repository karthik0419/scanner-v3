"""Backtest position sizing strategies over 3 years using v3 scanner signals.

This simulates running the v3 scanner weekly for 3 years, getting picks,
and applying different position sizing methods to see which produces
the best risk-adjusted returns.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

from telegram_notify import send_telegram, _get_credentials

# ─── Config ───
CAPITAL = 100000
YEARS = 3
END_DATE = datetime(2026, 8, 1)
START_DATE = END_DATE - timedelta(days=365 * YEARS)
MAX_POSITIONS = 17  # max concurrent positions (like current tracker)
ATR_MULT = 2.0
MAX_STOP_PCT = 8.0
T1_FRACTION = 0.50  # T1 = 50% of measured move
SCAN_INTERVAL_DAYS = 5  # scan every 5 days (weekly)
MIN_SCORE = 50
RE_ENTRY_WINDOW = 30
RE_ENTRY_STOP_PCT = 2.0

# ─── Stock universe ───
# Use backbone50 + nifty200 for speed
def load_universe():
    stocks = set()
    for f in ['backbone50.txt', 'nifty200.txt']:
        if os.path.exists(f):
            with open(f) as fh:
                for line in fh:
                    s = line.strip()
                    if s and not s.startswith('#'):
                        if not s.endswith('.NS'):
                            s = s + '.NS'
                        stocks.add(s)
    return sorted(stocks)

UNIVERSE = load_universe()
print(f"Universe: {len(UNIVERSE)} stocks")
print(f"Period: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')} ({YEARS} years)")
print()

# ─── Fetch all price data upfront ───
print("Fetching price data for all stocks...")

def fetch_all_prices(stocks, start, end):
    """Fetch historical data for all stocks, return dict of DataFrames."""
    data = {}
    failed = 0
    for i, sym in enumerate(stocks):
        try:
            h = yf.Ticker(sym).history(start=start.strftime('%Y-%m-%d'),
                                       end=end.strftime('%Y-%m-%d'), auto_adjust=True)
            if h is not None and len(h) > 100:
                if h.index.tz:
                    h.index = h.index.tz_localize(None)
                data[sym] = h
        except:
            failed += 1
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(stocks)} fetched ({len(data)} valid, {failed} failed)")
    print(f"  Done: {len(data)} stocks with valid data, {failed} failed")
    return data

PRICE_DATA = fetch_all_prices(UNIVERSE, START_DATE - timedelta(days=200), END_DATE + timedelta(days=30))

# ─── Pattern detection (simplified v3) ───
def detect_patterns(df, scan_date):
    """Detect Cup & Handle, Double Bottom, Descending Wedge on given date.
    Returns list of (pattern, breakout_level, stop, t1, t2, score) or None.
    """
    if df is None or len(df) < 60:
        return None

    # Get data up to scan_date
    mask = df.index <= scan_date
    if mask.sum() < 60:
        return None

    d = df[mask].copy()
    close = d['Close'].iloc[-1]
    high = d['High'].iloc[-1]
    low = d['Low'].iloc[-1]
    volume = d['Volume'].iloc[-1]

    # ATR
    tr = np.maximum(d['High'] - d['Low'],
                    np.maximum((d['High'] - d['Close'].shift(1)).abs(),
                               (d['Low'] - d['Close'].shift(1)).abs()))
    atr = tr.rolling(14).mean().iloc[-1]
    if np.isnan(atr) or atr == 0:
        return None

    # Moving averages
    sma_20 = d['Close'].rolling(20).mean().iloc[-1]
    sma_50 = d['Close'].rolling(50).mean().iloc[-1]
    if np.isnan(sma_20) or np.isnan(sma_50):
        return None

    # Volume average
    vol_avg_20 = d['Volume'].rolling(20).mean().iloc[-1]
    if vol_avg_20 == 0:
        return None

    patterns = []

    # ─── Cup & Handle ───
    # Look for cup (U-shape) followed by handle (small pullback)
    lookback = min(50, len(d) - 1)
    recent = d.tail(lookback)

    # Cup: find a high point, then a low, then recovery to near-high
    cup_high = recent['High'].iloc[:20].max() if len(recent) >= 20 else recent['High'].max()
    cup_low = recent['Low'].iloc[20:40].min() if len(recent) >= 40 else recent['Low'].min()
    cup_recovery = close

    # Handle: recent 5-10 days slight pullback
    handle_start = max(0, len(recent) - 10)
    handle_high = recent['High'].iloc[handle_start:].max()
    handle_low = recent['Low'].iloc[handle_start:].min()

    # Cup depth: 10-35%
    cup_depth = (cup_high - cup_low) / cup_high if cup_high > 0 else 0
    # Recovery: within 15% of cup high
    recovery_pct = (cup_recovery - cup_high) / cup_high if cup_high > 0 else -1

    if 0.10 <= cup_depth <= 0.40 and recovery_pct > -0.15:
        # Handle: pullback 5-12% from handle high
        handle_pullback = (handle_high - close) / handle_high if handle_high > 0 else 0
        if -0.02 <= handle_pullback <= 0.12:
            breakout = handle_high
            # Stop: below handle low or 2x ATR
            structural_stop = handle_low
            atr_stop = close - ATR_MULT * atr
            stop = max(structural_stop, atr_stop)
            # Cap stop at 8%
            min_stop = close * (1 - MAX_STOP_PCT / 100)
            if stop < min_stop:
                stop = min_stop

            risk = (close - stop) / close * 100
            if risk > 10 or risk < 1:
                pass
            else:
                # T1 = 50% of cup depth projected up from breakout
                measured_move = cup_high - cup_low
                t1 = breakout + measured_move * T1_FRACTION
                t2 = breakout + measured_move

                rr = (t1 - breakout) / (breakout - stop) if (breakout - stop) > 0 else 0

                # Score
                vol_ratio = volume / vol_avg_20
                score = 50
                if vol_ratio > 1.5:
                    score += 10
                if rr > 3:
                    score += 10
                if close > sma_20 > sma_50:
                    score += 10
                if cup_depth > 0.15:
                    score += 5

                # Status: NEAR if within 5%, BREAKOUT if above
                dist = (close - breakout) / breakout * 100
                if dist > 0:
                    status = 'BREAKOUT'
                    entry = close
                elif dist > -5:
                    status = 'NEAR'
                    entry = breakout
                else:
                    return patterns  # too far

                patterns.append({
                    'pattern': 'Cup & Handle',
                    'breakout': breakout,
                    'entry': entry,
                    'stop': stop,
                    't1': t1,
                    't2': t2,
                    'rr': rr,
                    'score': score,
                    'status': status,
                    'atr': atr,
                    'vol_ratio': vol_ratio,
                })

    # ─── Double Bottom ───
    # Two lows with a peak between them, second low >= first low
    lookback_db = min(40, len(d) - 1)
    recent_db = d.tail(lookback_db)

    if len(recent_db) >= 20:
        # Find two lows
        lows = recent_db['Low'].values
        mid = len(lows) // 2
        first_low = lows[:mid].min()
        first_low_idx = lows[:mid].argmin()
        second_low = lows[mid:].min()
        second_low_idx = mid + lows[mid:].argmin()
        peak = recent_db['High'].iloc[first_low_idx:second_low_idx].max() if second_low_idx > first_low_idx else 0

        # Double bottom: second low >= first low (within 3%)
        if peak > 0 and abs(second_low - first_low) / first_low < 0.03:
            breakout = peak
            if close > breakout * 0.95:  # within 5% of breakout
                structural_stop = min(first_low, second_low)
                atr_stop = close - ATR_MULT * atr
                stop = max(structural_stop, atr_stop)
                min_stop = close * (1 - MAX_STOP_PCT / 100)
                if stop < min_stop:
                    stop = min_stop

                risk = (close - stop) / close * 100
                if 1 <= risk <= 10:
                    measured_move = peak - min(first_low, second_low)
                    t1 = breakout + measured_move * T1_FRACTION
                    t2 = breakout + measured_move
                    rr = (t1 - breakout) / (breakout - stop) if (breakout - stop) > 0 else 0

                    vol_ratio = volume / vol_avg_20
                    score = 55  # Double Bottom gets bonus
                    if vol_ratio > 1.5:
                        score += 10
                    if rr > 3:
                        score += 10
                    if close > sma_20 > sma_50:
                        score += 10

                    dist = (close - breakout) / breakout * 100
                    if dist > 0:
                        status = 'BREAKOUT'
                        entry = close
                    elif dist > -5:
                        status = 'NEAR'
                        entry = breakout
                    else:
                        return patterns

                    patterns.append({
                        'pattern': 'Double Bottom',
                        'breakout': breakout,
                        'entry': entry,
                        'stop': stop,
                        't1': t1,
                        't2': t2,
                        'rr': rr,
                        'score': score,
                        'status': status,
                        'atr': atr,
                        'vol_ratio': vol_ratio,
                    })

    # ─── Descending Wedge ───
    # Lower highs, flat-ish lows, converging
    lookback_w = min(30, len(d) - 1)
    recent_w = d.tail(lookback_w)
    if len(recent_w) >= 15:
        highs = recent_w['High'].values
        lows = recent_w['Low'].values

        # Check for declining highs
        first_third = highs[:len(highs)//3].mean()
        last_third = highs[-len(highs)//3:].mean()
        first_third_lows = lows[:len(lows)//3].mean()
        last_third_lows = lows[-len(lows)//3:].mean()

        if last_third < first_third and abs(last_third_lows - first_third_lows) / first_third_lows < 0.05:
            breakout = recent_w['High'].max()
            if close > breakout * 0.95:
                structural_stop = recent_w['Low'].min()
                atr_stop = close - ATR_MULT * atr
                stop = max(structural_stop, atr_stop)
                min_stop = close * (1 - MAX_STOP_PCT / 100)
                if stop < min_stop:
                    stop = min_stop

                risk = (close - stop) / close * 100
                if 1 <= risk <= 10:
                    measured_move = breakout - recent_w['Low'].min()
                    t1 = breakout + measured_move * T1_FRACTION
                    t2 = breakout + measured_move
                    rr = (t1 - breakout) / (breakout - stop) if (breakout - stop) > 0 else 0

                    vol_ratio = volume / vol_avg_20
                    score = 45
                    if vol_ratio > 1.5:
                        score += 10
                    if rr > 3:
                        score += 10
                    if close > sma_20 > sma_50:
                        score += 10

                    dist = (close - breakout) / breakout * 100
                    if dist > 0:
                        status = 'BREAKOUT'
                        entry = close
                    elif dist > -5:
                        status = 'NEAR'
                        entry = breakout
                    else:
                        return patterns

                    patterns.append({
                        'pattern': 'Descending Wedge',
                        'breakout': breakout,
                        'entry': entry,
                        'stop': stop,
                        't1': t1,
                        't2': t2,
                        'rr': rr,
                        'score': score,
                        'status': status,
                        'atr': atr,
                        'vol_ratio': vol_ratio,
                    })

    return patterns


# ─── Trade simulation ───
class Trade:
    def __init__(self, symbol, entry_date, entry_price, stop, t1, t2, pattern, score, rr):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.stop = stop
        self.t1 = t1
        self.t2 = t2
        self.pattern = pattern
        self.score = score
        self.rr = rr
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.status = 'OPEN'
        self.shares = 0
        self.alloc_pct = 0
        self.stopped_out_breakout = None  # for re-entry

    def check_exit(self, df, current_date):
        """Check if trade hit SL, T1, or T2 on given date."""
        if self.status != 'OPEN':
            return

        mask = (df.index > self.entry_date) & (df.index <= current_date)
        period = df[mask]
        if len(period) == 0:
            return

        for idx, row in period.iterrows():
            # Check stop first (conservative)
            if row['Low'] <= self.stop:
                self.exit_date = idx
                self.exit_price = self.stop
                self.exit_reason = 'STOP'
                self.status = 'LOSS'
                self.stopped_out_breakout = self.entry_price  # remember for re-entry
                return
            # Check T2 (full exit)
            if row['High'] >= self.t2:
                self.exit_date = idx
                self.exit_price = self.t2
                self.exit_reason = 'T2'
                self.status = 'WIN_T2'
                return
            # Check T1 (partial exit - we'll simulate 50% at T1, 50% at T2)
            if row['High'] >= self.t1 and self.status == 'OPEN':
                # Mark as T1 hit - we'll handle partial exit in portfolio
                self.t1_hit_date = idx
                self.t1_hit_price = self.t1
                self.status = 'T1_HIT'

    def pnl_pct(self):
        if self.exit_price and self.entry_price:
            return (self.exit_price - self.entry_price) / self.entry_price * 100
        return 0


def run_backtest(sizing_method):
    """Run full backtest with given position sizing method.

    sizing_method: 'equal', 'score', 'rr', 'momentum', 'top5', 'top8', 'top10', 'risk_parity'
    """
    all_trades = []
    scan_dates = pd.date_range(START_DATE, END_DATE, freq=f'{SCAN_INTERVAL_DAYS}D')

    # Track active trades and capital
    active_trades = []
    closed_trades = []
    available_capital = CAPITAL
    capital_history = []

    for scan_date in scan_dates:
        # 1. Check exits on active trades
        still_active = []
        for trade in active_trades:
            df = PRICE_DATA.get(trade.symbol)
            if df is None:
                continue
            trade.check_exit(df, scan_date)

            if trade.status in ['LOSS', 'WIN_T2']:
                # Close trade - return capital
                if trade.status == 'LOSS':
                    exit_val = trade.shares * trade.exit_price
                    invested = trade.shares * trade.entry_price
                    available_capital += exit_val
                    closed_trades.append(trade)
                elif trade.status == 'WIN_T2':
                    exit_val = trade.shares * trade.exit_price
                    available_capital += exit_val
                    closed_trades.append(trade)

                # Check for re-entry if stopped out
                if trade.status == 'LOSS' and trade.stopped_out_breakout:
                    # Check if stock recovered above breakout within 30 days
                    df2 = PRICE_DATA.get(trade.symbol)
                    if df2 is not None:
                        future = df2[(df2.index > trade.exit_date) &
                                     (df2.index <= trade.exit_date + timedelta(days=RE_ENTRY_WINDOW))]
                        for idx2, row2 in future.iterrows():
                            if row2['High'] >= trade.stopped_out_breakout:
                                # Re-enter with tight stop
                                re_entry = row2['Close']
                                re_stop = trade.stopped_out_breakout * (1 - RE_ENTRY_STOP_PCT / 100)
                                re_trade = Trade(
                                    trade.symbol, idx2, re_entry, re_stop,
                                    trade.t1, trade.t2, trade.pattern + ' (RE-ENTRY)',
                                    trade.score, trade.rr
                                )
                                # Allocate to re-entry (smaller - 5% of capital)
                                re_alloc = min(available_capital * 0.05, available_capital)
                                re_trade.shares = int(re_alloc / re_entry)
                                if re_trade.shares > 0:
                                    available_capital -= re_trade.shares * re_entry
                                    re_trade.alloc_pct = re_alloc / CAPITAL * 100
                                    still_active.append(re_trade)
                                break
            elif trade.status == 'T1_HIT':
                # Partial exit at T1 (50% of shares)
                partial_shares = trade.shares // 2
                partial_value = partial_shares * trade.t1
                available_capital += partial_value
                trade.shares -= partial_shares
                trade.status = 'OPEN'  # continue holding rest for T2
                still_active.append(trade)
            else:
                still_active.append(trade)

        active_trades = still_active

        # 2. Time exit: trades held > 45 days
        still_active = []
        for trade in active_trades:
            days_held = (scan_date - trade.entry_date).days
            if days_held > 45:
                df = PRICE_DATA.get(trade.symbol)
                if df is not None:
                    mask = df.index <= scan_date
                    if mask.any():
                        trade.exit_price = float(df[mask]['Close'].iloc[-1])
                        trade.exit_date = scan_date
                        trade.exit_reason = 'TIME'
                        trade.status = 'TIME_EXIT'
                        available_capital += trade.shares * trade.exit_price
                        closed_trades.append(trade)
                        continue
            still_active.append(trade)
        active_trades = still_active

        # 3. Scan for new picks
        n_active = len(active_trades)
        slots = MAX_POSITIONS - n_active
        if slots <= 0:
            continue

        all_picks = []
        for sym in UNIVERSE:
            df = PRICE_DATA.get(sym)
            if df is None:
                continue
            patterns = detect_patterns(df, scan_date)
            if patterns:
                for p in patterns:
                    if p['score'] >= MIN_SCORE and p['status'] in ['BREAKOUT', 'NEAR']:
                        p['symbol'] = sym
                        all_picks.append(p)

        if not all_picks:
            continue

        # Sort by score, take top picks
        all_picks.sort(key=lambda x: x['score'], reverse=True)
        new_picks = all_picks[:slots]

        # Skip stocks already in active trades
        active_symbols = {t.symbol for t in active_trades}
        new_picks = [p for p in new_picks if p['symbol'] not in active_symbols]

        if not new_picks:
            continue

        # 4. Allocate capital based on sizing method
        if sizing_method == 'equal':
            weights = {p['symbol']: 1/len(new_picks) for p in new_picks}
        elif sizing_method == 'score':
            total_score = sum(p['score'] for p in new_picks)
            weights = {p['symbol']: p['score']/total_score for p in new_picks}
        elif sizing_method == 'rr':
            total_rr = sum(p['rr'] for p in new_picks)
            weights = {p['symbol']: p['rr']/total_rr for p in new_picks}
        elif sizing_method == 'momentum':
            # Weight by recent momentum (past 5-day return)
            weights = {}
            total_mom = 0
            for p in new_picks:
                df = PRICE_DATA.get(p['symbol'])
                if df is not None:
                    mask = df.index <= scan_date
                    recent = df[mask].tail(5)
                    if len(recent) >= 2:
                        mom = (recent['Close'].iloc[-1] / recent['Close'].iloc[0] - 1) * 100
                        mom = max(mom, -5) + 5  # shift to positive
                    else:
                        mom = 5
                else:
                    mom = 5
                weights[p['symbol']] = mom
                total_mom += mom
            weights = {k: v/total_mom for k, v in weights.items()}
        elif sizing_method == 'top5':
            new_picks = new_picks[:5]
            weights = {p['symbol']: 1/len(new_picks) for p in new_picks}
        elif sizing_method == 'top8':
            new_picks = new_picks[:8]
            weights = {p['symbol']: 1/len(new_picks) for p in new_picks}
        elif sizing_method == 'top10':
            new_picks = new_picks[:10]
            weights = {p['symbol']: 1/len(new_picks) for p in new_picks}
        elif sizing_method == 'risk_parity':
            # Equal risk: weight by 1/risk_pct
            weights = {}
            total_inv_risk = 0
            for p in new_picks:
                risk_pct = (p['entry'] - p['stop']) / p['entry'] * 100
                inv_risk = 1 / max(risk_pct, 1)
                weights[p['symbol']] = inv_risk
                total_inv_risk += inv_risk
            weights = {k: v/total_inv_risk for k, v in weights.items()}
        else:
            weights = {p['symbol']: 1/len(new_picks) for p in new_picks}

        # Enter trades
        for p in new_picks:
            alloc = available_capital * weights.get(p['symbol'], 0)
            shares = int(alloc / p['entry'])
            if shares == 0:
                continue

            trade = Trade(
                p['symbol'], scan_date, p['entry'], p['stop'],
                p['t1'], p['t2'], p['pattern'], p['score'], p['rr']
            )
            trade.shares = shares
            trade.alloc_pct = weights.get(p['symbol'], 0) * 100
            available_capital -= shares * p['entry']
            active_trades.append(trade)

        # Record portfolio value
        portfolio_val = available_capital
        for t in active_trades:
            df = PRICE_DATA.get(t.symbol)
            if df is not None:
                mask = df.index <= scan_date
                if mask.any():
                    portfolio_val += t.shares * float(df[mask]['Close'].iloc[-1])
        capital_history.append({
            'date': scan_date,
            'portfolio': portfolio_val,
            'cash': available_capital,
            'n_positions': len(active_trades),
        })

    # Close any remaining active trades at last price
    for trade in active_trades:
        df = PRICE_DATA.get(trade.symbol)
        if df is not None and len(df) > 0:
            trade.exit_price = float(df['Close'].iloc[-1])
            trade.exit_date = df.index[-1]
            trade.exit_reason = 'END'
            trade.status = 'END'
            available_capital += trade.shares * trade.exit_price
            closed_trades.append(trade)

    return closed_trades, pd.DataFrame(capital_history)


# ─── Run all strategies ───
strategies = ['equal', 'top5', 'top8', 'top10', 'score', 'rr', 'momentum', 'risk_parity']
results = {}

print("=" * 90)
print("  3-YEAR BACKTEST — Position Sizing Strategies (Rs 1,00,000 capital)")
print("=" * 90)
print()

for strat in strategies:
    print("Running: %s ..." % strat, end=' ', flush=True)
    trades, hist = run_backtest(strat)

    # Calculate metrics
    n_trades = len(trades)
    if n_trades == 0:
        print("No trades!")
        continue

    wins = [t for t in trades if t.status in ['WIN_T2', 'T1_HIT']]
    losses = [t for t in trades if t.status == 'LOSS']
    time_exits = [t for t in trades if t.status in ['TIME_EXIT', 'END']]

    win_rate = len(wins) / n_trades * 100 if n_trades > 0 else 0

    # Calculate returns
    final_capital = hist['portfolio'].iloc[-1] if len(hist) > 0 else CAPITAL
    total_return = (final_capital - CAPITAL) / CAPITAL * 100
    cagr = ((final_capital / CAPITAL) ** (1/YEARS) - 1) * 100 if final_capital > 0 else -100

    # Max drawdown
    if len(hist) > 0:
        peak = hist['portfolio'].cummax()
        dd = (hist['portfolio'] - peak) / peak * 100
        max_dd = dd.min()
    else:
        max_dd = 0

    # Avg P&L per trade
    pnls = [t.pnl_pct() for t in trades]
    avg_pnl = np.mean(pnls) if pnls else 0
    avg_win = np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0
    avg_loss = np.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0

    # Profit factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else 999

    # Sharpe (simplified)
    if len(hist) > 10:
        returns = hist['portfolio'].pct_change().dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    else:
        sharpe = 0

    results[strat] = {
        'n_trades': n_trades,
        'win_rate': win_rate,
        'final_capital': final_capital,
        'total_return': total_return,
        'cagr': cagr,
        'max_dd': max_dd,
        'avg_pnl': avg_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'pf': pf,
        'sharpe': sharpe,
        'n_wins': len(wins),
        'n_losses': len(losses),
    }

    print("done. %d trades, return: %+.1f%%" % (n_trades, total_return))

# ─── Print comparison ───
print()
print("=" * 100)
print("  RESULTS COMPARISON")
print("=" * 100)
print()
print("  %-20s  %6s  %6s  %8s  %8s  %8s  %8s  %6s  %6s  %6s  %6s" % (
    "Strategy", "Trades", "Win%", "Return%", "CAGR%", "MaxDD%", "AvgP&L%", "PF", "Sharpe", "AvgWin", "AvgLoss"))
print("  " + "-" * 110)

for strat in strategies:
    if strat not in results:
        continue
    r = results[strat]
    print("  %-20s  %6d  %5.1f  %+7.1f  %+7.1f  %7.1f  %+7.2f  %5.2f  %6.2f  %+5.1f  %+5.1f" % (
        strat, r['n_trades'], r['win_rate'], r['total_return'], r['cagr'],
        r['max_dd'], r['avg_pnl'], r['pf'], r['sharpe'],
        r['avg_win'], r['avg_loss']))

# Rank by return
print()
print("  " + "=" * 100)
print("  RANKING BY TOTAL RETURN")
print("  " + "=" * 100)
ranked = sorted(results.items(), key=lambda x: x[1]['total_return'], reverse=True)
for i, (strat, r) in enumerate(ranked):
    print("  %d. %-20s  Return: %+.1f%%  CAGR: %+.1f%%  MaxDD: %.1f%%  PF: %.2f  Sharpe: %.2f" % (
        i+1, strat, r['total_return'], r['cagr'], r['max_dd'], r['pf'], r['sharpe']))

# Rank by risk-adjusted (return / abs(max_dd))
print()
print("  " + "=" * 100)
print("  RANKING BY RISK-ADJUSTED (Return / |MaxDD|)")
print("  " + "=" * 100)
ranked_ra = sorted(results.items(),
                   key=lambda x: x[1]['total_return'] / abs(x[1]['max_dd']) if x[1]['max_dd'] != 0 else 0,
                   reverse=True)
for i, (strat, r) in enumerate(ranked_ra):
    ratio = r['total_return'] / abs(r['max_dd']) if r['max_dd'] != 0 else 0
    print("  %d. %-20s  Ret/MaxDD = %.2f  (Return %+.1f%% / DD %.1f%%)" % (
        i+1, strat, ratio, r['total_return'], r['max_dd']))

# Rank by Sharpe
print()
print("  " + "=" * 100)
print("  RANKING BY SHARPE RATIO")
print("  " + "=" * 100)
ranked_sh = sorted(results.items(), key=lambda x: x[1]['sharpe'], reverse=True)
for i, (strat, r) in enumerate(ranked_sh):
    print("  %d. %-20s  Sharpe: %.2f  (Return %+.1f%%, MaxDD %.1f%%)" % (
        i+1, strat, r['sharpe'], r['total_return'], r['max_dd']))

# Bank FD comparison
fd_return = 7 * YEARS
fd_value = CAPITAL * (1 + fd_return / 100)
print()
print("  " + "=" * 100)
print("  BENCHMARK: Bank FD @ 7%%/year for %d years" % YEARS)
print("  FD value: Rs %s  (Return: +%.1f%%)" % (format(fd_value, ',.0f'), fd_return))
print("  " + "=" * 100)

# Best strategy detail
best_strat = ranked[0][0]
best = results[best_strat]
print()
print("  BEST STRATEGY: %s" % best_strat)
print("  Final capital: Rs %s" % format(best['final_capital'], ',.0f'))
print("  Total return:  %+.1f%%" % best['total_return'])
print("  CAGR:          %+.1f%%" % best['cagr'])
print("  Max drawdown:  %.1f%%" % best['max_dd'])
print("  Win rate:      %.1f%%" % best['win_rate'])
print("  Profit factor: %.2f" % best['pf'])
print("  Sharpe:        %.2f" % best['sharpe'])
print("  Trades:        %d (%d wins, %d losses)" % (best['n_trades'], best['n_wins'], best['n_losses']))

# Send to Telegram
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>3-Year Backtest — Position Sizing Strategies</b>")
    lines.append("<b>Rs 1,00,000 | %d stocks | Jul 2023 - Aug 2026</b>" % len(UNIVERSE))
    lines.append("")
    lines.append("<b>RESULTS (ranked by return)</b>")
    lines.append("%-14s  %5s  %6s  %7s  %6s  %5s  %6s" % ("Strategy", "Trades", "Win%", "Return%", "MaxDD%", "PF", "Sharpe"))
    lines.append("-" * 65)
    for i, (strat, r) in enumerate(ranked):
        lines.append("%-14s  %5d  %5.1f  %+6.1f  %5.1f  %5.2f  %6.2f" % (
            strat, r['n_trades'], r['win_rate'], r['total_return'], r['max_dd'], r['pf'], r['sharpe']))

    lines.append("")
    lines.append("<b>BEST: %s</b>" % ranked[0][0])
    lines.append("  Return: %+.1f%%  CAGR: %+.1f%%" % (ranked[0][1]['total_return'], ranked[0][1]['cagr']))
    lines.append("  MaxDD: %.1f%%  PF: %.2f  Sharpe: %.2f" % (ranked[0][1]['max_dd'], ranked[0][1]['pf'], ranked[0][1]['sharpe']))
    lines.append("")
    lines.append("<b>BEST RISK-ADJUSTED: %s</b>" % ranked_ra[0][0])
    lines.append("  Ret/MaxDD: %.2f  (Return %+.1f%% / DD %.1f%%)" % (
        ranked_ra[0][1]['total_return'] / abs(ranked_ra[0][1]['max_dd']),
        ranked_ra[0][1]['total_return'], ranked_ra[0][1]['max_dd']))
    lines.append("")
    lines.append("<b>BEST SHARPE: %s</b>" % ranked_sh[0][0])
    lines.append("  Sharpe: %.2f  Return: %+.1f%%" % (ranked_sh[0][1]['sharpe'], ranked_sh[0][1]['total_return']))
    lines.append("")
    lines.append("Bank FD @7%% x %d years: +%.1f%%" % (YEARS, fd_return))
    lines.append("")
    lines.append("Not financial advice. For research only.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print("\n  [Telegram] %s" % ("Sent" if ok else "Failed"))
