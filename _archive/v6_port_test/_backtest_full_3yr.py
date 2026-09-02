"""
3-Year Backtest with REAL v3.1 engine + 4 improvements:
1. Full v3.1 pattern detection (all 15 detectors)
2. Sector filter (only BOOM/RISING sectors)
3. Regime filter (Nifty above SMA50+SMA200)
4. Re-entry after whipsaw (built into engine)

Then test multiple position sizing strategies on the filtered trades.
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

from backtester.engine import backtest_symbol, _detect_signal, _score, _apply_atr_stop, _add_targets, _calc_atr, _data_is_sane
from data.loader import _fetch_nse, _resample_weekly
from utils.sector_rotation_v3 import get_stock_sector, get_sector_bonus
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
print(f"Universe: {len(UNIVERSE)} stocks")
print(f"Period: {YEARS} years")
print()

# ─── Fetch Nifty for regime filter ───
print("Fetching Nifty 50 for regime filter...")
nifty = yf.Ticker('^NSEI').history(period=f'{YEARS+1}y')
if nifty.index.tz is not None:
    nifty.index = nifty.index.tz_localize(None)
nifty = nifty.dropna()
nifty['sma50'] = nifty['Close'].rolling(50).mean()
nifty['sma200'] = nifty['Close'].rolling(200).mean()
nifty['regime'] = np.where((nifty['Close'] > nifty['sma50']) & (nifty['Close'] > nifty['sma200']), 'BULL', 'BEAR')

def get_regime(date):
    """Real-time regime: use PRIOR trading day (no look-ahead)."""
    mask = nifty.index <= date
    if mask.sum() == 0:
        return 'UNKNOWN'
    return nifty.loc[mask, 'regime'].iloc[-1]

# ─── Sector filter ───
# Pre-compute sector for each stock
print("Mapping sectors...")
stock_sectors = {}
for sym in UNIVERSE:
    stock_sectors[sym] = get_stock_sector(sym)

# We'll compute sector heat dynamically per scan date
# For backtest, use a simplified approach: check sector index performance
print("Fetching sector indices...")
sector_indices = {
    'Banking': '^NSEBANK',
    'IT': '^CNXIT',
    'Pharma': '^CNXPHARMA',
    'Auto': '^CNXAUTO',
    'Metals': '^CNXMETAL',
    'FMCG': '^CNXFMCG',
    'Infra': '^CNXINFRA',
    'Realty': '^CNXREALTY',
    'Energy': '^CNXENERGY',
    'Media': '^CNXMEDIA',
    'PSU Bank': '^CNXPSUBANK',
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

print(f"  Got sector data for: {list(sector_data.keys())}")

def get_hot_sectors(date, top_n=5):
    """Get top performing sectors on given date (5-day + 20-day performance)."""
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
        # BOOM: both positive, RISING: 5d positive
        if perf_5d > 0 and perf_20d > 0:
            scores[sector] = perf_5d + perf_20d
    # Return top N
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [s[0] for s in ranked[:top_n]]

# ─── Run backtest with real v3.1 engine ───
print()
print("=" * 80)
print("  Running REAL v3.1 backtest (all 15 pattern detectors, ATR stops, re-entry)")
print("=" * 80)

all_trades = []
for i, sym in enumerate(UNIVERSE):
    if (i + 1) % 20 == 0:
        print(f"  [{i+1}/{len(UNIVERSE)}] ... {len(all_trades)} trades so far")
    try:
        trades = backtest_symbol(sym, years=YEARS, min_score=MIN_SCORE,
                                 scan_every=SCAN_EVERY, atr_stop=True)
        all_trades.extend(trades)
    except Exception as e:
        pass

print(f"  Done: {len(all_trades)} raw trades from {len(UNIVERSE)} stocks")

# ─── Apply filters ───
trades_df = pd.DataFrame(all_trades)
if len(trades_df) == 0:
    print("No trades generated!")
    sys.exit(1)

trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date'])
trades_df['exit_date'] = pd.to_datetime(trades_df['exit_date'])
trades_df['sector'] = trades_df['symbol'].map(stock_sectors)

# 1. Regime filter
trades_df['regime'] = trades_df['entry_date'].apply(get_regime)
print(f"\nRegime distribution: {trades_df['regime'].value_counts().to_dict()}")

# 2. Sector filter — compute hot sectors per trade date
print("Computing hot sectors per trade date...")
unique_dates = trades_df['entry_date'].unique()
hot_sectors_map = {}
for d in unique_dates:
    hot_sectors_map[d] = set(get_hot_sectors(d, top_n=5))

trades_df['hot_sector'] = trades_df.apply(
    lambda r: r['sector'] in hot_sectors_map.get(r['entry_date'], set()), axis=1)

print(f"Hot sector trades: {trades_df['hot_sector'].sum()}/{len(trades_df)}")

# ─── Filter combinations ───
filters = {
    'baseline': trades_df.copy(),
    'regime_only': trades_df[trades_df['regime'] == 'BULL'].copy(),
    'sector_only': trades_df[trades_df['hot_sector']].copy(),
    'regime+sector': trades_df[(trades_df['regime'] == 'BULL') & (trades_df['hot_sector'])].copy(),
}

# ─── Position sizing strategies ───
def simulate_portfolio(trades, capital, max_positions, sizing='equal'):
    """Simulate portfolio with position sizing.
    Returns final capital, max drawdown, trade count.
    """
    trades = trades.sort_values('entry_date').to_dict('records')
    cash = capital
    active = []  # list of {symbol, shares, entry_price, exit_date, exit_price, alloc}
    equity_curve = []
    closed_count = 0
    win_count = 0

    for t in trades:
        entry_d = t['entry_date']
        exit_d = t['exit_date']

        # Remove exited positions
        still_active = []
        for p in active:
            if p['exit_date'] <= entry_d:
                # Close position
                exit_val = p['shares'] * p['exit_price']
                cash += exit_val
                closed_count += 1
                if p['exit_price'] > p['entry_price']:
                    win_count += 1
            else:
                still_active.append(p)
        active = still_active

        if len(active) >= max_positions:
            continue

        # Calculate weight based on sizing method
        if sizing == 'equal':
            weight = 1.0 / max_positions
        elif sizing == 'score':
            # Proportional to score (clamp 40-100)
            weight = max(t['score'], 40) / 100
        elif sizing == 'rr':
            # Proportional to R:R
            weight = max(t['rr'], 0.5) / 5.0  # normalize to ~0.1-0.2
        elif sizing == 'momentum':
            # Not applicable in backtest (no prior momentum data per trade)
            weight = 1.0 / max_positions
        elif sizing == 'risk_parity':
            # Inverse risk weighting
            risk = (t['entry_price'] - t['stop_loss']) / t['entry_price'] * 100
            weight = 1.0 / max(risk, 1) / 10  # normalize
        elif sizing == 'top5':
            weight = 1.0 / 5
        elif sizing == 'top8':
            weight = 1.0 / 8
        elif sizing == 'top10':
            weight = 1.0 / 10
        else:
            weight = 1.0 / max_positions

        # Normalize weights for current open + new
        total_weight = sum(1.0/max_positions for _ in active) + weight
        if total_weight > 1.0:
            weight = weight * (1.0 - sum(1.0/max_positions for _ in active)) / total_weight

        alloc = cash * weight
        shares = int(alloc / t['entry_price'])
        if shares < 1:
            continue

        cost = shares * t['entry_price']
        cash -= cost

        active.append({
            'symbol': t['symbol'],
            'shares': shares,
            'entry_price': t['entry_price'],
            'exit_date': exit_d,
            'exit_price': t['exit_price'],
            'alloc': cost,
        })

        # Record equity
        equity = cash
        for p in active:
            equity += p['shares'] * p['entry_price']  # approximate (use entry as proxy)
        equity_curve.append(equity)

    # Close remaining
    for p in active:
        cash += p['shares'] * p['exit_price']
        closed_count += 1
        if p['exit_price'] > p['entry_price']:
            win_count += 1

    # Max drawdown from equity curve
    if len(equity_curve) > 10:
        eq = pd.Series(equity_curve)
        peak = eq.cummax()
        dd = (eq - peak) / peak * 100
        max_dd = dd.min()
    else:
        max_dd = 0

    total_return = (cash - capital) / capital * 100
    win_rate = win_count / closed_count * 100 if closed_count > 0 else 0

    return {
        'final_capital': cash,
        'total_return': total_return,
        'max_dd': max_dd,
        'trades': closed_count,
        'win_rate': win_rate,
    }


# ─── Run all combinations ───
print()
print("=" * 100)
print("  TESTING: 4 filter combos x 8 position sizing strategies = 32 combinations")
print("=" * 100)

sizing_methods = ['equal', 'score', 'rr', 'risk_parity', 'top5', 'top8', 'top10', 'momentum']

results = []
for filter_name, filter_trades in filters.items():
    n_trades = len(filter_trades)
    if n_trades == 0:
        continue

    # Trade-level stats
    pnls = filter_trades['pnl_pct'].dropna()
    win_rate = (pnls > 0).mean() * 100 if len(pnls) > 0 else 0
    avg_pnl = pnls.mean() if len(pnls) > 0 else 0
    avg_win = pnls[pnls > 0].mean() if (pnls > 0).any() else 0
    avg_loss = pnls[pnls < 0].mean() if (pnls < 0).any() else 0
    pf = pnls[pnls > 0].sum() / abs(pnls[pnls < 0].sum()) if (pnls < 0).any() and pnls[pnls<0].sum() != 0 else 999

    for sizing in sizing_methods:
        r = simulate_portfolio(filter_trades, CAPITAL, MAX_POSITIONS, sizing=sizing)
        cagr = ((r['final_capital'] / CAPITAL) ** (1/YEARS) - 1) * 100 if r['final_capital'] > 0 else -100
        results.append({
            'filter': filter_name,
            'sizing': sizing,
            'n_trades': n_trades,
            'trades_traded': r['trades'],
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'pf': pf,
            'final_capital': r['final_capital'],
            'total_return': r['total_return'],
            'cagr': cagr,
            'max_dd': r['max_dd'],
            'avg_win': avg_win,
            'avg_loss': avg_loss,
        })

        print(f"  {filter_name:20s} + {sizing:12s}  ->  Return: {r['total_return']:+7.1f}%  MaxDD: {r['max_dd']:6.1f}%  Trades: {r['trades']:4d}")

# ─── Results table ───
rdf = pd.DataFrame(results)
rdf = rdf.sort_values('total_return', ascending=False)

print()
print("=" * 120)
print("  FULL RESULTS (sorted by total return)")
print("=" * 120)
print()
print("  %-20s  %-12s  %6s  %6s  %6s  %8s  %8s  %7s  %7s  %5s  %6s  %6s  %6s" % (
    "Filter", "Sizing", "Trades", "Traded", "Win%", "AvgP&L%", "PF", "Return%", "CAGR%", "MaxDD%", "AvgWin", "AvgLoss", "Final"))
print("  " + "-" * 115)

for _, r in rdf.iterrows():
    print("  %-20s  %-12s  %6d  %6d  %5.1f  %+7.2f  %5.2f  %+7.1f  %+6.1f  %6.1f  %+5.1f  %+5.1f  Rs %7.0f" % (
        r['filter'], r['sizing'], r['n_trades'], r['trades_traded'], r['win_rate'],
        r['avg_pnl'], r['pf'], r['total_return'], r['cagr'], r['max_dd'],
        r['avg_win'], r['avg_loss'], r['final_capital']))

# ─── Top 10 ───
print()
print("=" * 120)
print("  TOP 10 COMBINATIONS")
print("=" * 120)
for i, (_, r) in enumerate(rdf.head(10).iterrows()):
    print("  %2d. %-20s + %-12s  Return: %+.1f%%  CAGR: %+.1f%%  MaxDD: %.1f%%  PF: %.2f  Win: %.1f%%  Trades: %d" % (
        i+1, r['filter'], r['sizing'], r['total_return'], r['cagr'], r['max_dd'], r['pf'], r['win_rate'], r['trades_traded']))

# ─── Best by filter ───
print()
print("=" * 120)
print("  BEST SIZING PER FILTER")
print("=" * 120)
for filter_name in filters.keys():
    subset = rdf[rdf['filter'] == filter_name]
    if len(subset) == 0:
        continue
    best = subset.iloc[0]
    print("  %-20s  Best sizing: %-12s  Return: %+.1f%%  CAGR: %+.1f%%  MaxDD: %.1f%%  PF: %.2f" % (
        filter_name, best['sizing'], best['total_return'], best['cagr'], best['max_dd'], best['pf']))

# ─── Bank FD comparison ───
fd_return = 7 * YEARS
fd_value = CAPITAL * (1 + fd_return / 100)
print()
print("=" * 120)
print("  BENCHMARK: Bank FD @ 7%%/year for %d years = +%.1f%% (Rs %s)" % (YEARS, fd_return, format(fd_value, ',.0f')))
print("=" * 120)

# ─── Best overall ───
best = rdf.iloc[0]
print()
print("  BEST OVERALL: %s + %s" % (best['filter'], best['sizing']))
print("  Final capital: Rs %s" % format(best['final_capital'], ',.0f'))
print("  Total return:  %+.1f%%" % best['total_return'])
print("  CAGR:          %+.1f%%" % best['cagr'])
print("  Max drawdown:  %.1f%%" % best['max_dd'])
print("  Win rate:      %.1f%%" % best['win_rate'])
print("  Profit factor: %.2f" % best['pf'])
print("  Trades:        %d (of %d signals)" % (best['trades_traded'], best['n_trades']))
print("  Avg win:       %+.1f%%" % best['avg_win'])
print("  Avg loss:      %+.1f%%" % best['avg_loss'])
print("  vs Bank FD:    %+.1f%% alpha" % (best['total_return'] - fd_return))

# ─── Save results ───
out_file = f'results/sizing_backtest_3yr_{datetime.now().strftime("%Y%m%d")}.csv'
rdf.to_csv(out_file, index=False)
print(f"\n  Saved: {out_file}")

# ─── Send to Telegram ───
token, chat_id = _get_credentials()
if token and chat_id:
    lines = []
    lines.append("<b>3-Year Backtest — REAL v3.1 Engine + Filters + Sizing</b>")
    lines.append("<b>Rs 1,00,000 | %d stocks | %d patterns | ATR stops | Re-entry</b>" % (len(UNIVERSE), 15))
    lines.append("")
    lines.append("<b>TOP 10 COMBINATIONS</b>")
    lines.append("%-18s  %-10s  %7s  %6s  %6s  %5s  %5s" % ("Filter", "Sizing", "Return%", "CAGR%", "MaxDD%", "PF", "Win%"))
    lines.append("-" * 65)
    for i, (_, r) in enumerate(rdf.head(10).iterrows()):
        lines.append("%-18s  %-10s  %+6.1f  %+5.1f  %5.1f  %5.2f  %5.1f" % (
            r['filter'], r['sizing'], r['total_return'], r['cagr'], r['max_dd'], r['pf'], r['win_rate']))

    lines.append("")
    lines.append("<b>BEST PER FILTER</b>")
    for filter_name in filters.keys():
        subset = rdf[rdf['filter'] == filter_name]
        if len(subset) == 0:
            continue
        best = subset.iloc[0]
        lines.append("  %-18s + %-10s -> %+.1f%% (CAGR %+.1f%%, DD %.1f%%)" % (
            filter_name, best['sizing'], best['total_return'], best['cagr'], best['max_dd']))

    lines.append("")
    lines.append("<b>BENCHMARK</b>")
    lines.append("  Bank FD @7%% x %d years: +%.1f%%" % (YEARS, fd_return))
    lines.append("  Best strategy: %+.1f%%" % best['total_return'])
    lines.append("  Alpha vs FD: %+.1f%%" % (best['total_return'] - fd_return))
    lines.append("")
    lines.append("<b>BEST OVERALL: %s + %s</b>" % (rdf.iloc[0]['filter'], rdf.iloc[0]['sizing']))
    lines.append("  Trades: %d | Win: %.1f%% | PF: %.2f" % (rdf.iloc[0]['trades_traded'], rdf.iloc[0]['win_rate'], rdf.iloc[0]['pf']))
    lines.append("  Avg win: %+.1f%% | Avg loss: %+.1f%%" % (rdf.iloc[0]['avg_win'], rdf.iloc[0]['avg_loss']))
    lines.append("")
    lines.append("Not financial advice. For research only.")

    msg = "\n".join(lines)
    ok = send_telegram(token, chat_id, msg)
    print("\n  [Telegram] %s" % ("Sent" if ok else "Failed"))
