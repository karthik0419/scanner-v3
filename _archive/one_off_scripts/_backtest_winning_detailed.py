"""
Detailed backtest of the WINNING strategy:
  - Regime filter (Nifty above SMA50+SMA200)
  - Sector filter (top 5 hot sectors)
  - Equal weight position sizing
  - 17 max positions
  - Real v3.1 engine (15 patterns, ATR stops, re-entry)

Produces: year-by-year, monthly, worst/best trades, drawdown periods.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from backtester.engine import backtest_symbol
from utils.sector_rotation_v3 import get_stock_sector
from telegram_notify import send_telegram, _get_credentials

# ─── Config ───
CAPITAL = 100000
YEARS = 3
MAX_POSITIONS = 17
MIN_SCORE = 50
SCAN_EVERY = 5

# ─── Load universe ───
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
print(f"Universe: {len(UNIVERSE)} stocks, {YEARS} years")

# ─── Fetch Nifty for regime ───
print("Fetching Nifty 50...")
nifty = yf.Ticker('^NSEI').history(period=f'{YEARS+1}y')
if nifty.index.tz is not None:
    nifty.index = nifty.index.tz_localize(None)
nifty = nifty.dropna()
nifty['sma50'] = nifty['Close'].rolling(50).mean()
nifty['sma200'] = nifty['Close'].rolling(200).mean()
nifty['regime'] = np.where((nifty['Close'] > nifty['sma50']) & (nifty['Close'] > nifty['sma200']), 'BULL', 'BEAR')

def get_regime(date):
    mask = nifty.index <= date
    if mask.sum() == 0:
        return 'UNKNOWN'
    return nifty.loc[mask, 'regime'].iloc[-1]

# ─── Sector filter ───
print("Mapping sectors...")
stock_sectors = {}
for sym in UNIVERSE:
    stock_sectors[sym] = get_stock_sector(sym)

print("Fetching sector indices...")
sector_indices = {
    'Banking': '^NSEBANK', 'IT': '^CNXIT', 'Pharma': '^CNXPHARMA',
    'Auto': '^CNXAUTO', 'Metals': '^CNXMETAL', 'FMCG': '^CNXFMCG',
    'Infra': '^CNXINFRA', 'Realty': '^CNXREALTY', 'Energy': '^CNXENERGY',
    'Media': '^CNXMEDIA', 'PSU Bank': '^CNXPSUBANK',
    'Financial Services': '^NSEBANK',
}
sector_data = {}
for sector, idx_sym in sector_indices.items():
    try:
        h = yf.Ticker(idx_sym).history(period=f'{YEARS+1}y')
        if h is not None and len(h) > 100:
            if h.index.tz:
                h.index = h.index.tz_localize(None)
            sector_data[sector] = h
    except:
        pass

def get_hot_sectors(date, top_n=5):
    scores = {}
    for sector, h in sector_data.items():
        mask = h.index <= date
        if mask.sum() < 25:
            continue
        recent = h[mask].tail(25)
        if len(recent) < 25:
            continue
        perf_5d = (recent['Close'].iloc[-1] / recent['Close'].iloc[-6] - 1) * 100 if len(recent) >= 6 else 0
        perf_20d = (recent['Close'].iloc[-1] / recent['Close'].iloc[-21] - 1) * 100 if len(recent) >= 21 else 0
        if perf_5d > 0 and perf_20d > 0:
            scores[sector] = perf_5d + perf_20d
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [s[0] for s in ranked[:top_n]]

# ─── Run backtest ───
print()
print("Running v3.1 backtest on all stocks...")
all_trades = []
for i, sym in enumerate(UNIVERSE):
    if (i + 1) % 30 == 0:
        print(f"  [{i+1}/{len(UNIVERSE)}] {len(all_trades)} trades")
    try:
        trades = backtest_symbol(sym, years=YEARS, min_score=MIN_SCORE,
                                 scan_every=SCAN_EVERY, atr_stop=True)
        all_trades.extend(trades)
    except:
        pass

print(f"  Done: {len(all_trades)} raw trades")

trades_df = pd.DataFrame(all_trades)
trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date'])
trades_df['exit_date'] = pd.to_datetime(trades_df['exit_date'])
trades_df['sector'] = trades_df['symbol'].map(stock_sectors)

# Apply regime filter
trades_df['regime'] = trades_df['entry_date'].apply(get_regime)

# Apply sector filter
print("Computing hot sectors...")
unique_dates = trades_df['entry_date'].unique()
hot_sectors_map = {}
for d in unique_dates:
    hot_sectors_map[d] = set(get_hot_sectors(d, top_n=5))

trades_df['hot_sector'] = trades_df.apply(
    lambda r: r['sector'] in hot_sectors_map.get(r['entry_date'], set()), axis=1)

# Filter: regime+sector
filtered = trades_df[(trades_df['regime'] == 'BULL') & (trades_df['hot_sector'])].copy()
print(f"Filtered trades: {len(filtered)} (from {len(trades_df)} raw)")

# ─── Portfolio simulation (equal weight, 17 max positions) ───
def simulate_detailed(trades, capital, max_positions):
    """Detailed simulation with equity curve, monthly returns, trade log."""
    trades = trades.sort_values('entry_date').to_dict('records')
    cash = capital
    active = []
    equity_curve = []
    trade_log = []
    monthly_returns = {}

    for t in trades:
        entry_d = t['entry_date']
        exit_d = t['exit_date']

        # Close exited positions
        still_active = []
        for p in active:
            if p['exit_date'] <= entry_d:
                exit_val = p['shares'] * p['exit_price']
                cash += exit_val
                pnl = (p['exit_price'] - p['entry_price']) / p['entry_price'] * 100
                trade_log.append({
                    'symbol': p['symbol'],
                    'pattern': p['pattern'],
                    'entry_date': p['entry_date'],
                    'exit_date': p['exit_date'],
                    'entry_price': p['entry_price'],
                    'exit_price': p['exit_price'],
                    'shares': p['shares'],
                    'invested': p['shares'] * p['entry_price'],
                    'exit_value': exit_val,
                    'pnl_rs': exit_val - p['shares'] * p['entry_price'],
                    'pnl_pct': pnl,
                    'result': 'WIN' if pnl > 0 else 'LOSS',
                    'exit_reason': p.get('exit_reason', ''),
                    'days_held': (p['exit_date'] - p['entry_date']).days,
                    'sector': p.get('sector', ''),
                })
            else:
                still_active.append(p)
        active = still_active

        if len(active) >= max_positions:
            continue

        # Equal weight
        alloc = cash / max_positions
        shares = int(alloc / t['entry_price'])
        if shares < 1:
            continue

        cost = shares * t['entry_price']
        cash -= cost

        active.append({
            'symbol': t['symbol'],
            'pattern': t['pattern'],
            'shares': shares,
            'entry_price': t['entry_price'],
            'exit_date': exit_d,
            'exit_price': t['exit_price'],
            'exit_reason': t.get('exit_reason', ''),
            'sector': t.get('sector', stock_sectors.get(t['symbol'], '')),
            'entry_date': entry_d,
        })

        # Record equity (approximate using entry prices)
        equity = cash + sum(p['shares'] * p['entry_price'] for p in active)
        equity_curve.append({'date': entry_d, 'equity': equity, 'cash': cash, 'positions': len(active)})

    # Close remaining
    for p in active:
        exit_val = p['shares'] * p['exit_price']
        cash += exit_val
        pnl = (p['exit_price'] - p['entry_price']) / p['entry_price'] * 100
        trade_log.append({
            'symbol': p['symbol'],
            'pattern': p['pattern'],
            'entry_date': p['entry_date'],
            'exit_date': p['exit_date'],
            'entry_price': p['entry_price'],
            'exit_price': p['exit_price'],
            'shares': p['shares'],
            'invested': p['shares'] * p['entry_price'],
            'exit_value': exit_val,
            'pnl_rs': exit_val - p['shares'] * p['entry_price'],
            'pnl_pct': pnl,
            'result': 'WIN' if pnl > 0 else 'LOSS',
            'exit_reason': p.get('exit_reason', ''),
            'days_held': (p['exit_date'] - p['entry_date']).days,
            'sector': p.get('sector', ''),
        })

    return cash, trade_log, pd.DataFrame(equity_curve)

print()
print("Simulating portfolio...")
final_capital, trade_log, equity_curve = simulate_detailed(filtered, CAPITAL, MAX_POSITIONS)
trade_log_df = pd.DataFrame(trade_log)

total_return = (final_capital - CAPITAL) / CAPITAL * 100
cagr = ((final_capital / CAPITAL) ** (1/YEARS) - 1) * 100 if final_capital > 0 else -100

print(f"  Final capital: Rs {final_capital:,.0f}")
print(f"  Total return: {total_return:+.1f}%")
print(f"  CAGR: {cagr:+.1f}%")
print(f"  Trades: {len(trade_log_df)}")

# ─── Year-by-year breakdown ───
print()
print("=" * 100)
print("  YEAR-BY-YEAR BREAKDOWN")
print("=" * 100)
trade_log_df['year'] = trade_log_df['exit_date'].dt.year
trade_log_df['month'] = trade_log_df['exit_date'].dt.to_period('M')

yearly = trade_log_df.groupby('year').agg(
    trades=('symbol', 'count'),
    wins=('result', lambda x: (x == 'WIN').sum()),
    losses=('result', lambda x: (x == 'LOSS').sum()),
    total_pnl=('pnl_rs', 'sum'),
    avg_pnl_pct=('pnl_pct', 'mean'),
    best_trade=('pnl_pct', 'max'),
    worst_trade=('pnl_pct', 'min'),
).reset_index()

yearly['win_rate'] = yearly['wins'] / yearly['trades'] * 100
yearly['cumulative_pnl'] = yearly['total_pnl'].cumsum()
yearly['cumulative_return'] = yearly['cumulative_pnl'] / CAPITAL * 100

print()
print("  %-6s  %6s  %5s  %5s  %6s  %9s  %8s  %8s  %8s  %9s  %9s" % (
    "Year", "Trades", "Wins", "Loss", "Win%", "P&L Rs", "AvgP&L%", "Best%", "Worst%", "Cum P&L", "Cum Ret%"))
print("  " + "-" * 100)
for _, y in yearly.iterrows():
    print("  %-6d  %6d  %5d  %5d  %5.1f  Rs %7.0f  %+7.2f  %+7.1f  %+7.1f  Rs %7.0f  %+8.1f" % (
        y['year'], y['trades'], y['wins'], y['losses'], y['win_rate'],
        y['total_pnl'], y['avg_pnl_pct'], y['best_trade'], y['worst_trade'],
        y['cumulative_pnl'], y['cumulative_return']))

# ─── Monthly returns ───
print()
print("=" * 100)
print("  MONTHLY RETURNS")
print("=" * 100)
monthly = trade_log_df.groupby('month').agg(
    trades=('symbol', 'count'),
    pnl_rs=('pnl_rs', 'sum'),
    win_rate=('result', lambda x: (x == 'WIN').mean() * 100),
).reset_index()
monthly['return_pct'] = monthly['pnl_rs'] / CAPITAL * 100

print()
print("  %-10s  %6s  %9s  %8s  %8s" % ("Month", "Trades", "P&L Rs", "Return%", "Win%"))
print("  " + "-" * 50)
for _, m in monthly.iterrows():
    bar = "+" * int(max(m['return_pct'], 0)) + "-" * int(max(-m['return_pct'], 0))
    print("  %-10s  %6d  Rs %7.0f  %+7.2f  %6.1f  %s" % (
        str(m['month']), m['trades'], m['pnl_rs'], m['return_pct'], m['win_rate'], bar[:30]))

# ─── Best and worst trades ───
print()
print("=" * 100)
print("  TOP 10 BEST TRADES")
print("=" * 100)
print("  %-16s  %-20s  %10s  %10s  %7s  %5s  %-12s" % (
    "Symbol", "Pattern", "Entry", "Exit", "P&L%", "Days", "Exit Reason"))
print("  " + "-" * 90)
for _, t in trade_log_df.nlargest(10, 'pnl_pct').iterrows():
    print("  %-16s  %-20s  Rs %7.2f  Rs %7.2f  %+6.1f  %4d  %s" % (
        t['symbol'], t['pattern'][:20], t['entry_price'], t['exit_price'],
        t['pnl_pct'], t['days_held'], t['exit_reason']))

print()
print("=" * 100)
print("  TOP 10 WORST TRADES")
print("=" * 100)
print("  %-16s  %-20s  %10s  %10s  %7s  %5s  %-12s" % (
    "Symbol", "Pattern", "Entry", "Exit", "P&L%", "Days", "Exit Reason"))
print("  " + "-" * 90)
for _, t in trade_log_df.nsmallest(10, 'pnl_pct').iterrows():
    print("  %-16s  %-20s  Rs %7.2f  Rs %7.2f  %+6.1f  %4d  %s" % (
        t['symbol'], t['pattern'][:20], t['entry_price'], t['exit_price'],
        t['pnl_pct'], t['days_held'], t['exit_reason']))

# ─── By pattern ───
print()
print("=" * 100)
print("  BY PATTERN")
print("=" * 100)
by_pattern = trade_log_df.groupby('pattern').agg(
    trades=('symbol', 'count'),
    win_rate=('result', lambda x: (x == 'WIN').mean() * 100),
    avg_pnl=('pnl_pct', 'mean'),
    total_pnl=('pnl_rs', 'sum'),
).reset_index().sort_values('total_pnl', ascending=False)

print()
print("  %-25s  %6s  %6s  %8s  %9s" % ("Pattern", "Trades", "Win%", "AvgP&L%", "Total P&L"))
print("  " + "-" * 60)
for _, p in by_pattern.iterrows():
    print("  %-25s  %6d  %5.1f  %+7.2f  Rs %7.0f" % (
        p['pattern'][:25], p['trades'], p['win_rate'], p['avg_pnl'], p['total_pnl']))

# ─── By exit reason ───
print()
print("=" * 100)
print("  BY EXIT REASON")
print("=" * 100)
by_exit = trade_log_df.groupby('exit_reason').agg(
    trades=('symbol', 'count'),
    win_rate=('result', lambda x: (x == 'WIN').mean() * 100),
    avg_pnl=('pnl_pct', 'mean'),
    total_pnl=('pnl_rs', 'sum'),
).reset_index().sort_values('trades', ascending=False)

print()
print("  %-20s  %6s  %6s  %8s  %9s" % ("Exit Reason", "Trades", "Win%", "AvgP&L%", "Total P&L"))
print("  " + "-" * 55)
for _, e in by_exit.iterrows():
    print("  %-20s  %6d  %5.1f  %+7.2f  Rs %7.0f" % (
        e['exit_reason'][:20], e['trades'], e['win_rate'], e['avg_pnl'], e['total_pnl']))

# ─── By sector ───
print()
print("=" * 100)
print("  BY SECTOR")
print("=" * 100)
by_sector = trade_log_df.groupby('sector').agg(
    trades=('symbol', 'count'),
    win_rate=('result', lambda x: (x == 'WIN').mean() * 100),
    avg_pnl=('pnl_pct', 'mean'),
    total_pnl=('pnl_rs', 'sum'),
).reset_index().sort_values('total_pnl', ascending=False)

print()
print("  %-20s  %6s  %6s  %8s  %9s" % ("Sector", "Trades", "Win%", "AvgP&L%", "Total P&L"))
print("  " + "-" * 55)
for _, s in by_sector.iterrows():
    print("  %-20s  %6d  %5.1f  %+7.2f  Rs %7.0f" % (
        s['sector'][:20], s['trades'], s['win_rate'], s['avg_pnl'], s['total_pnl']))

# ─── Drawdown analysis ───
print()
print("=" * 100)
print("  DRAWDOWN ANALYSIS")
print("=" * 100)
if len(equity_curve) > 10:
    eq = equity_curve['equity']
    peak = eq.cummax()
    dd = (eq - peak) / peak * 100
    max_dd = dd.min()
    max_dd_date = equity_curve.loc[dd.idxmin(), 'date']

    # Find drawdown periods
    in_dd = dd < -1
    dd_periods = []
    start = None
    for i in range(len(in_dd)):
        if in_dd.iloc[i] and start is None:
            start = i
        elif not in_dd.iloc[i] and start is not None:
            dd_periods.append((start, i-1, dd.iloc[start:i+1].min()))
            start = None
    if start is not None:
        dd_periods.append((start, len(in_dd)-1, dd.iloc[start:].min()))

    print(f"  Max drawdown: {max_dd:.1f}%")
    print(f"  Max DD date: {max_dd_date.strftime('%Y-%m-%d')}")
    print(f"  Number of DD periods (>1%): {len(dd_periods)}")
    print()
    print("  Top 5 drawdown periods:")
    dd_periods.sort(key=lambda x: x[2])
    for i, (s, e, d) in enumerate(dd_periods[:5]):
        s_date = equity_curve.iloc[s]['date'].strftime('%Y-%m-%d')
        e_date = equity_curve.iloc[e]['date'].strftime('%Y-%m-%d')
        duration = (equity_curve.iloc[e]['date'] - equity_curve.iloc[s]['date']).days
        print("    %d. %s to %s  |  DD: %.1f%%  |  Duration: %d days" % (i+1, s_date, e_date, d, duration))

# ─── Summary stats ───
print()
print("=" * 100)
print("  FULL SUMMARY")
print("=" * 100)
pnls = trade_log_df['pnl_pct']
wins = trade_log_df[trade_log_df['result'] == 'WIN']
losses = trade_log_df[trade_log_df['result'] == 'LOSS']

print(f"  Capital:          Rs {CAPITAL:,}")
print(f"  Final capital:    Rs {final_capital:,.0f}")
print(f"  Total return:     {total_return:+.1f}%")
print(f"  CAGR:             {cagr:+.1f}%")
print(f"  Max drawdown:     {max_dd:.1f}%")
print(f"  Total trades:     {len(trade_log_df)}")
print(f"  Wins:             {len(wins)}  ({len(wins)/len(trade_log_df)*100:.1f}%)")
print(f"  Losses:           {len(losses)}  ({len(losses)/len(trade_log_df)*100:.1f}%)")
print(f"  Avg win:          {wins['pnl_pct'].mean():+.1f}%")
print(f"  Avg loss:         {losses['pnl_pct'].mean():+.1f}%")
print(f"  Avg P&L/trade:    {pnls.mean():+.2f}%")
print(f"  Profit factor:    {wins['pnl_pct'].sum() / abs(losses['pnl_pct'].sum()):.2f}")
print(f"  Avg days held:    {trade_log_df['days_held'].mean():.1f}")
print(f"  Best trade:       {pnls.max():+.1f}% ({trade_log_df.loc[pnls.idxmax(), 'symbol']})")
print(f"  Worst trade:      {pnls.min():+.1f}% ({trade_log_df.loc[pnls.idxmin(), 'symbol']})")
print(f"  Bank FD (7% x {YEARS}y): +{7*YEARS:.0f}%")
print(f"  Alpha vs FD:      {total_return - 7*YEARS:+.1f}%")

# ─── Save ───
out = f'results/winning_strategy_detailed_{datetime.now().strftime("%Y%m%d")}.csv'
trade_log_df.to_csv(out, index=False)
print(f"\n  Saved: {out}")

# ─── Send to Telegram ───
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>Detailed Backtest — Winning Strategy</b>")
    lines.append("<b>Regime+Sector filter | Equal weight | 17 max pos | Real v3.1</b>")
    lines.append(f"<b>Rs 1,00,000 | {YEARS} years | {len(UNIVERSE)} stocks</b>")
    lines.append("")
    lines.append("<b>SUMMARY</b>")
    lines.append(f"  Final: Rs {final_capital:,.0f}  |  Return: {total_return:+.1f}%")
    lines.append(f"  CAGR: {cagr:+.1f}%  |  MaxDD: {max_dd:.1f}%")
    lines.append(f"  Trades: {len(trade_log_df)}  |  Win: {len(wins)/len(trade_log_df)*100:.1f}%")
    lines.append(f"  PF: {wins['pnl_pct'].sum() / abs(losses['pnl_pct'].sum()):.2f}")
    lines.append(f"  Avg win: {wins['pnl_pct'].mean():+.1f}%  |  Avg loss: {losses['pnl_pct'].mean():+.1f}%")
    lines.append(f"  Bank FD: +{7*YEARS:.0f}%  |  Alpha: {total_return - 7*YEARS:+.1f}%")
    lines.append("")
    lines.append("<b>YEAR-BY-YEAR</b>")
    for _, y in yearly.iterrows():
        lines.append(f"  {y['year']}: {y['trades']} trades, WR {y['win_rate']:.0f}%, P&L Rs {y['total_pnl']:+.0f} ({y['avg_pnl_pct']:+.1f}%/trade), Cum {y['cumulative_return']:+.1f}%")
    lines.append("")
    lines.append("<b>BY PATTERN (top 5)</b>")
    for _, p in by_pattern.head(5).iterrows():
        lines.append(f"  {p['pattern'][:20]:20s}  {p['trades']}t  WR {p['win_rate']:.0f}%  {p['avg_pnl']:+.1f}%  Rs {p['total_pnl']:+.0f}")
    lines.append("")
    lines.append("<b>BY EXIT REASON</b>")
    for _, e in by_exit.iterrows():
        lines.append(f"  {e['exit_reason'][:18]:18s}  {e['trades']}t  WR {e['win_rate']:.0f}%  {e['avg_pnl']:+.1f}%")
    lines.append("")
    lines.append("<b>BEST 5 TRADES</b>")
    for _, t in trade_log_df.nlargest(5, 'pnl_pct').iterrows():
        lines.append(f"  {t['symbol']:14s}  {t['pnl_pct']:+5.1f}%  {t['days_held']}d  {t['exit_reason']}")
    lines.append("")
    lines.append("<b>WORST 5 TRADES</b>")
    for _, t in trade_log_df.nsmallest(5, 'pnl_pct').iterrows():
        lines.append(f"  {t['symbol']:14s}  {t['pnl_pct']:+5.1f}%  {t['days_held']}d  {t['exit_reason']}")
    lines.append("")
    lines.append("<b>MAX DRAWDOWN</b>")
    lines.append(f"  {max_dd:.1f}% on {max_dd_date.strftime('%Y-%m-%d')}")
    lines.append(f"  DD periods >1%: {len(dd_periods)}")
    lines.append("")
    lines.append("Not financial advice. For research only.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print(f"\n  [Telegram] {'Sent' if ok else 'Failed'}")
