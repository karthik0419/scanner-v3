"""
Daily Morning Scanner v3
Run every morning before market opens (or after close).

What it does:
  1. Checks all NSE sector indices — finds today's top 2 hot sectors
  2. Loads backbone 50 + hot sector stocks
  3. Checks volume surge (>2x avg) + price vs breakout level
  4. Prints a clean actionable watchlist
  5. v3: Price range filter (--min-price 100 --max-price 400)
  6. v3: Bearish mode — finds weak sectors + stocks with selling pressure

Usage:
  python daily_scan.py              # auto-detect hot sectors
  python daily_scan.py --sector METAL   # force a specific sector
  python daily_scan.py --top 20         # show top 20 instead of default 15
  python daily_scan.py --min-price 100 --max-price 400   # retail filter
  python daily_scan.py --bearish        # find weak sectors + short candidates
"""

import os, sys, warnings, argparse
warnings.filterwarnings("ignore")
import logging
for n in ["yfinance", "urllib3"]: logging.getLogger(n).setLevel(logging.CRITICAL)

import yfinance as yf
import pandas as pd
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

# Telegram notification (auto-sends after scan completes)
from telegram_notify import send_daily_summary

# Sector mapping (uses NSE official data + yfinance fallback)
from utils.sector_rotation_v3 import get_stock_sector, STOCK_SECTOR

# ── SECTOR INDICES (NSE) ────────────────────────────────────────────────────
SECTOR_INDICES = {
    "METAL":   "^CNXMETAL",
    "AUTO":    "^CNXAUTO",
    "BANK":    "^NSEBANK",
    "IT":      "^CNXIT",
    "PHARMA":  "^CNXPHARMA",
    "FMCG":    "^CNXFMCG",
    "REALTY":  "^CNXREALTY",
    "ENERGY":  "^CNXENERGY",
    "INFRA":   "^CNXINFRA",
    "MEDIA":   "^CNXMEDIA",
    "PSU":     "^CNXPSE",
    "MIDCAP":  "^CNXMIDCAP",
}

# ── SECTOR STOCK LISTS ──────────────────────────────────────────────────────
SECTOR_STOCKS = {
    "METAL": [
        "HINDALCO","JSWSTEEL","TATASTEEL","VEDL","SAIL","NMDC","COALINDIA",
        "APLAPOLLO","HINDZINC","NATIONALUM","JINDALSTEL","RATNAMANI",
        "MOIL","WELCORP","HINDCOPPER","SHYAMMETL","APL","GALLANTT",
    ],
    "AUTO": [
        "MARUTI","TATAMOTORS","M&M","BAJAJ-AUTO","HEROMOTOCO","EICHERMOT",
        "TVSMOTOR","ASHOKLEY","BOSCHLTD","MOTHERSON","BALKRISIND",
        "BHARATFORG","MRF","TIINDIA","APOLLOTYRE","CRAFTSMAN","ENDURANCE",
    ],
    "BANK": [
        "HDFCBANK","ICICIBANK","KOTAKBANK","AXISBANK","SBIN","INDUSINDBK",
        "FEDERALBNK","BANDHANBNK","IDFCFIRSTB","PNB","BANKBARODA","CANBK",
        "RBLBANK","AUBANK","DCBBANK","KARURVYSYA","CUB",
    ],
    "IT": [
        "TCS","INFY","HCLTECH","WIPRO","TECHM","LTIM","COFORGE","MPHASIS",
        "PERSISTENT","KPITTECH","OFSS","NIITLTD","MASTEK","CYIENT","BSOFT",
    ],
    "PHARMA": [
        "SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","BIOCON","AUROPHARMA",
        "TORNTPHARM","LUPIN","ALKEM","IPCALAB","GLENMARK","NATCOPHARM",
        "GRANULES","SUVEN","LAUREATE",
    ],
    "FMCG": [
        "HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR","GODREJCP",
        "MARICO","COLPAL","EMAMILTD","TATACONSUM","VBL","RADICO",
        "MCDOWELL-N","UNITEDSPIRIT","GILLETTE",
    ],
    "REALTY": [
        "DLF","GODREJPROP","OBEROIRLTY","PHOENIXLTD","PRESTIGE","SOBHA",
        "BRIGADE","KOLTEPATIL","SUNTECK","MAHINDCIE","LODHA","SIGNATURE",
    ],
    "ENERGY": [
        "RELIANCE","ONGC","BPCL","IOC","NTPC","TATAPOWER","ADANIGREEN",
        "POWERGRID","TORNTPOWER","SUZLON","CESC","SJVN","NHPC",
        "GREENKO","ADANIPOWER",
    ],
    "INFRA": [
        "LT","ADANIPORTS","ULTRACEMCO","GRASIM","BHARTIARTL","INDIGO",
        "CONCOR","GMRINFRA","IRB","KNRCON","PNC","HGINFRA","PNCINFRA",
        "NBCC","NCC","TECHNO",
    ],
    "MEDIA": [
        "PVRINOX","SUNTV","ZEEL","NETWORK18","TVTODAY","JAGRAN","DISHTV",
    ],
    "PSU": [
        "ONGC","COALINDIA","POWERGRID","NTPC","SBIN","PNB","BANKBARODA",
        "BEL","HAL","BHEL","SAIL","NMDC","IRFC","RECLTD","PFC",
    ],
    "MIDCAP": [
        "COFORGE","PERSISTENT","KPITTECH","ROUTE","CDSL","BSE","TANLA",
        "FIVESTAR","EASEMYTRIP","CAMPUS","BIKAJI","LATENTVIEW",
    ],
}

# ── BACKBONE 50 (from backbone50.txt) ──────────────────────────────────────
BACKBONE = [
    "BHARATFORG","SCHAEFFLER","TIMKEN","SKFINDIA","AIAENG","CRAFTSMAN",
    "CUMMINSIND","THERMAX","ELGIEQUIP","CARBORUNIV","RKFORGE","CIEINDIA",
    "ENDURANCE","GRINDWELL","TATACOMM","STLTECH","HFCL","INDUSTOWER",
    "CDSL","BSE","ROUTE","TANLA","COFORGE","PERSISTENT","MPHASIS",
    "KPITTECH","RAILTEL","ABB","SIEMENS","HAVELLS","POLYCAB","POWERGRID",
    "TATAPOWER","TORNTPOWER","NTPC","ADANIGREEN","SUZLON","BLUESTARCO",
    "VOLTAS","AMBER","EXIDEIND","AMARAJABAT","TEJASNET","ITI","NELCO",
    "ROSSARI","SHAKTIPUMP","POCL","VINDHYATEL","GTLINFRA",
]


# ── DYNAMIC STOCK LOADING ─────────────────────────────────────────────────
def _load_weekly_scan_picks(max_stocks=50):
    """Read top stocks from the latest weekly scan CSV.
    These are fresh pattern setups that need daily monitoring for entry triggers."""
    import glob
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    files = [f for f in glob.glob(os.path.join(results_dir, "v3_*.csv")) if "_all" not in f]
    if not files:
        files = [f for f in glob.glob(os.path.join(results_dir, "v2_*.csv")) if "_all" not in f]
    if not files:
        return []
    files.sort(key=lambda f: os.path.getmtime(f))
    try:
        df = pd.read_csv(files[-1])
        syms = df["symbol"].head(max_stocks).tolist()
        # Strip .NS suffix
        return [s.replace(".NS", "").replace(".BO", "") for s in syms]
    except Exception:
        return []


def _load_weekly_scan_df():
    """Load the latest weekly scan CSV as a DataFrame.
    Returns (df, path) or (None, None) if not found."""
    import glob
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    files = [f for f in glob.glob(os.path.join(results_dir, "v3_*.csv")) if "_all" not in f]
    if not files:
        return None, None
    files.sort(key=lambda f: os.path.getmtime(f))
    try:
        df = pd.read_csv(files[-1])
        return df, files[-1]
    except Exception:
        return None, None


def _compute_freshness(current_csv_path, current_symbols, lookback_days=7):
    """Check how many consecutive previous daily scan CSVs contained each symbol.

    For each symbol in current_symbols, returns:
      'NEW'      — not in any previous scan CSV (first time flagged)
      'Day N'    — appeared in N consecutive previous CSVs (including today)

    Args:
        current_csv_path: path to today's CSV (excluded from lookback)
        current_symbols: list of symbol strings (normalized, no .NS)
        lookback_days: how many previous CSVs to check (default 7)

    Returns:
        dict: {symbol: 'NEW' or 'Day N'}
    """
    import glob
    from datetime import datetime, timedelta

    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    all_files = [f for f in glob.glob(os.path.join(results_dir, "v3_*.csv"))
                 if "_all" not in f]
    # Sort by mtime descending (newest first)
    all_files.sort(key=os.path.getmtime, reverse=True)

    # Exclude the current CSV, take the next `lookback_days` files
    prev_files = []
    for f in all_files:
        if os.path.abspath(f) == os.path.abspath(current_csv_path):
            continue
        prev_files.append(f)
        if len(prev_files) >= lookback_days:
            break

    # Load each previous CSV's symbols (normalized)
    prev_symbol_sets = []
    for f in prev_files:
        try:
            prev_df = pd.read_csv(f)
            prev_syms = set(_normalize_symbol(str(s)) for s in prev_df["symbol"])
            prev_symbol_sets.append(prev_syms)
        except Exception:
            break  # stop if a CSV can't be read

    freshness = {}
    for sym in current_symbols:
        days = 0
        for prev_set in prev_symbol_sets:
            if sym in prev_set:
                days += 1
            else:
                break  # stop at first gap (consecutive only)
        if days == 0:
            freshness[sym] = "NEW"
        else:
            freshness[sym] = f"Day {days + 1}"  # +1 for today

    return freshness


def _load_nifty500():
    """Load Nifty 500 stocks for broad coverage of liquid stocks."""
    fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nifty500.txt")
    try:
        with open(fpath) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return []


def _build_dynamic_universe(use_weekly_picks=True, use_nifty500=True):
    """Build the daily scan universe from three sources:
    1. Backbone 50 (stable momentum stocks — always watched)
    2. Latest weekly scan picks (fresh pattern setups — changes every scan)
    3. Nifty 500 (broad coverage of liquid stocks)
    Plus hot/weak sector stocks based on today's sector performance.
    Returns (all_symbols, weekly_picks, nifty500_count) tuple.
    """
    stocks = list(BACKBONE)  # start with backbone

    weekly_picks = []
    if use_weekly_picks:
        weekly_picks = _load_weekly_scan_picks(max_stocks=50)
        stocks.extend(weekly_picks)

    nifty500 = []
    if use_nifty500:
        nifty500 = _load_nifty500()
        stocks.extend(nifty500)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for s in stocks:
        s_clean = s.strip().upper()
        if s_clean and s_clean not in seen:
            seen.add(s_clean)
            unique.append(s_clean)

    return unique, len(weekly_picks), len(nifty500)


def _get_stocks_in_sectors(sector_names):
    """Get ALL stocks in the given sectors from the NSE sector map.

    Uses data/nse_sectors.json (568+ stocks) instead of the hardcoded
    SECTOR_STOCKS dict which only had ~15 stocks per sector.

    Args:
        sector_names: list of sector names (e.g. ['Banking', 'IT'])
                      or NSE index names (e.g. ['BANK', 'IT'])
    Returns: list of stock symbols (without .NS suffix)
    """
    # Map NSE index names to our sector names
    SECTOR_NAME_MAP = {
        'METAL': 'Metals', 'AUTO': 'Auto', 'BANK': 'Banking',
        'IT': 'IT', 'PHARMA': 'Pharma', 'FMCG': 'FMCG',
        'REALTY': 'Realty', 'ENERGY': 'Energy', 'INFRA': 'Infra',
        'MEDIA': 'Media', 'PSU': 'PSU Bank', 'MIDCAP': 'MidCap',
    }

    target_sectors = set()
    for s in sector_names:
        s_upper = s.upper()
        mapped = SECTOR_NAME_MAP.get(s_upper, s.capitalize())
        target_sectors.add(mapped)

    # Look up all stocks in these sectors from the NSE sector map
    stocks = []
    for sym_ns, sector in STOCK_SECTOR.items():
        if sector in target_sectors:
            stocks.append(sym_ns.replace('.NS', ''))

    return stocks


def _build_smart_universe(hot_sectors, use_weekly_picks=True, use_nifty500=True):
    """Build a SMART daily scan universe — catches most movers without scanning all 2000+.

    Sources (combined & deduplicated):
    1. Backbone 50 (always watched)
    2. Nifty 500 (broad liquid stock coverage)
    3. Latest weekly scan picks (fresh pattern setups)
    4. ALL stocks in today's hot sectors (from NSE sector map — 50-100+ per sector)
       This is the key upgrade: instead of ~15 hardcoded stocks per hot sector,
       we now get ALL stocks in that sector from the 568-stock NSE mapping.

    Args:
        hot_sectors: list of sector names that are hot today (e.g. ['BANK', 'IT'])
    Returns: (all_symbols, breakdown_dict)
    """
    stocks = list(BACKBONE)
    breakdown = {'backbone': len(BACKBONE), 'weekly': 0, 'nifty500': 0, 'hot_sector': 0}

    # Weekly picks
    if use_weekly_picks:
        weekly = _load_weekly_scan_picks(max_stocks=50)
        stocks.extend(weekly)
        breakdown['weekly'] = len(weekly)

    # Nifty 500
    if use_nifty500:
        n500 = _load_nifty500()
        stocks.extend(n500)
        breakdown['nifty500'] = len(n500)

    # All stocks in hot sectors (from NSE sector map — much larger than hardcoded list)
    hot_sector_stocks = _get_stocks_in_sectors(hot_sectors)
    stocks.extend(hot_sector_stocks)
    breakdown['hot_sector'] = len(hot_sector_stocks)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for s in stocks:
        s_clean = s.strip().upper()
        if s_clean and s_clean not in seen:
            seen.add(s_clean)
            unique.append(s_clean)

    return unique, breakdown

SURGE_THRESHOLD = 1.8   # volume > 1.8x 20-day avg


def get_sector_performance():
    """Returns list of (sector, pct_change_today, last_price) sorted best first.

    Primary source: jugaad-data NSELive.all_indices() (no rate limiting).
    Fallback: yfinance sector index tickers (rate-limited, may fail).
    """
    # ── Primary: NSE live via jugaad-data ──
    # Map NSE index symbols to our sector names
    NSE_INDEX_MAP = {
        "NIFTY METAL":    "METAL",
        "NIFTY AUTO":     "AUTO",
        "NIFTY BANK":     "BANK",
        "NIFTY IT":       "IT",
        "NIFTY PHARMA":   "PHARMA",
        "NIFTY FMCG":     "FMCG",
        "NIFTY REALTY":   "REALTY",
        "NIFTY ENERGY":   "ENERGY",
        "NIFTY INFRA":    "INFRA",
        "NIFTY MEDIA":    "MEDIA",
        "NIFTY PSE":      "PSU",
        "NIFTY MIDCAP 50":"MIDCAP",
    }
    try:
        from jugaad_data import nse
        live = nse.NSELive()
        all_idx = live.all_indices()
        if isinstance(all_idx, dict) and 'data' in all_idx:
            results = []
            for idx in all_idx['data']:
                sym = idx.get('indexSymbol', '')
                sector = NSE_INDEX_MAP.get(sym)
                if sector:
                    pct = round(float(idx.get('percentChange', 0)), 2)
                    last = float(idx.get('last', 0))
                    results.append((sector, pct, last))
            if results:
                return sorted(results, key=lambda x: x[1], reverse=True)
    except Exception:
        pass

    # ── Fallback: yfinance (may be rate-limited) ──
    results = []
    for sector, ticker in SECTOR_INDICES.items():
        try:
            t = yf.Ticker(ticker)
            fi = t.fast_info
            cur  = float(fi.last_price)
            prev = float(fi.regular_market_previous_close)
            if cur and prev and prev > 0:
                pct = round((cur - prev) / prev * 100, 2)
                results.append((sector, pct, cur))
        except Exception:
            pass
    return sorted(results, key=lambda x: x[1], reverse=True)


def get_price_info(symbol):
    """Fetch last close, volume, 20d avg volume, + compute trade plan (entry/SL/target/RR).

    Trade plan logic:
    - Entry: current close (for BREAKOUT) or today's high (for WATCH — buy on breakout)
    - Stop loss: max(today's low, close - 2.0*ATR) — structural + ATR hybrid, 8% max cap
    - Target: entry + 2 * (entry - stop) — 2:1 R:R minimum
    - R:R: (target - entry) / (entry - stop)
    """
    sym_ns = symbol + ".NS" if not symbol.endswith(".NS") else symbol
    try:
        hist = yf.Ticker(sym_ns).history(period="30d", auto_adjust=False)
        if hist is None or len(hist) < 5:
            return None
        hist = hist.dropna(subset=["Close", "Volume"])
        if len(hist) < 5:
            return None
        cur_close  = float(hist["Close"].iloc[-1])
        cur_vol    = float(hist["Volume"].iloc[-1])
        avg_vol    = float(hist["Volume"].tail(21).iloc[:-1].mean())
        prev_close = float(hist["Close"].iloc[-2])
        pct_chg    = round((cur_close - prev_close) / prev_close * 100, 2)
        vol_ratio  = round(cur_vol / avg_vol, 1) if avg_vol > 0 else 0

        # Today's high/low for structural stop
        today_high = float(hist["High"].iloc[-1])
        today_low  = float(hist["Low"].iloc[-1])

        # 14-day ATR for volatility-based stop
        atr = 0.0
        if len(hist) >= 15:
            tr_values = []
            for i in range(1, min(15, len(hist))):
                h  = float(hist["High"].iloc[i])
                l  = float(hist["Low"].iloc[i])
                pc = float(hist["Close"].iloc[i-1])
                tr = max(h - l, abs(h - pc), abs(l - pc))
                tr_values.append(tr)
            atr = sum(tr_values) / len(tr_values) if tr_values else 0.0

        # ── Trade plan ──
        # Entry: current close (you'd enter at market on breakout confirmation)
        entry = cur_close
        # Stop: structural (today's low) or ATR-based (close - 2.0*ATR), whichever is tighter
        # 2.0x ATR chosen after multiplier sweep: PF 2.03 vs 1.80 at 1.5x, DD -46.8% vs -66.7%
        stop_atr   = cur_close - 2.0 * atr if atr > 0 else cur_close * 0.95
        stop_struct = today_low
        stop = max(stop_struct, stop_atr)  # tighter stop = less risk
        # Max 8% stop cap (v3 protocol — prevents catastrophic losses on wide-range days)
        max_stop = entry * 0.92
        stop = max(stop, max_stop)
        if stop >= entry:  # edge case: stock already below stop
            stop = entry * 0.97
        # Target: 2:1 R:R
        risk   = entry - stop
        target = entry + 2 * risk
        rr     = round((target - entry) / risk, 1) if risk > 0 else 0

        return {
            "symbol":    symbol,
            "close":     round(cur_close, 2),
            "pct_chg":   pct_chg,
            "vol_ratio": vol_ratio,
            "avg_vol":   round(avg_vol / 1e5, 1),   # in lakhs
            "cur_vol":   round(cur_vol / 1e5, 1),
            # Trade plan
            "entry":     round(entry, 2),
            "stop":      round(stop, 2),
            "target":    round(target, 2),
            "rr":        rr,
            "risk_pct":  round(risk / entry * 100, 1) if entry > 0 else 0,
            "today_high": round(today_high, 2),
            "today_low":  round(today_low, 2),
            "atr":        round(atr, 2),
        }
    except Exception:
        return None


def run_scan(symbols, label="", workers=8):
    """Scan stocks for price + volume info. Uses thread pool for speed.

    Args:
        symbols: list of stock symbols (without .NS)
        label: label for progress printing
        workers: number of parallel threads (default 8)
    """
    results = []
    total = len(symbols)
    if total == 0:
        return results

    print(f"  Scanning {total} stocks ({label})..." + (f" [{workers} threads]" if workers > 1 else ""))

    if workers <= 1:
        # Sequential mode (for debugging)
        for i, sym in enumerate(symbols):
            print(f"  [{i+1}/{total}] {sym:<15}", end="\r")
            info = get_price_info(sym)
            if info:
                results.append(info)
        print(" " * 40, end="\r")
        return results

    # Parallel mode — thread pool
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(get_price_info, sym): sym for sym in symbols}
        for future in as_completed(futures):
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  [{done}/{total}] scanned", end="\r")
            info = future.result()
            if info:
                results.append(info)
    print(" " * 40, end="\r")
    return results


def print_results(results, title, top=15):
    # Sort: volume surge first, then by % change
    surges   = [r for r in results if r["vol_ratio"] >= SURGE_THRESHOLD]
    movers   = [r for r in results if r["vol_ratio"] < SURGE_THRESHOLD]
    surges.sort(key=lambda x: x["vol_ratio"], reverse=True)
    movers.sort(key=lambda x: x["pct_chg"], reverse=True)
    combined = surges + movers

    print(f"\n{'='*70}")
    print(f"  {title}  (top {min(top, len(combined))} of {len(combined)})")
    print(f"{'='*70}")
    print(f"  {'Stock':<14} {'Close':>8} {'Chg%':>7} {'Vol(L)':>8} {'AvgVol':>8} {'VolRatio':>9}  Alert")
    print(f"  {'-'*65}")

    shown = 0
    for r in combined[:top]:
        sym      = r["symbol"]
        close    = r["close"]
        pct      = r["pct_chg"]
        vr       = r["vol_ratio"]
        cv       = r["cur_vol"]
        av       = r["avg_vol"]

        pct_str  = ('+' if pct >= 0 else '') + str(pct) + '%'
        vr_str   = str(vr) + 'x'

        if vr >= 3.0:
            alert = "FIRE  *** volume explosion"
        elif vr >= SURGE_THRESHOLD:
            alert = "SURGE ** watch closely"
        elif pct >= 3:
            alert = "MOVER * strong up day"
        else:
            alert = ""

        print(f"  {sym:<14} {close:>8.2f} {pct_str:>7} {cv:>8.1f} {av:>8.1f} {vr_str:>9}  {alert}")
        shown += 1

    if shown == 0:
        print("  No data available.")


def _normalize_symbol(sym):
    """Strip .NS suffix for consistent dedup."""
    return sym.replace(".NS", "").strip()


def _categorize_pick(r):
    """Classify a stock by price action + volume into an actionable category.

    Returns one of: BREAKOUT, BREAKDOWN, MISSED_UP, MISSED_DOWN, WATCH, FLAT
    """
    pct = r["pct_chg"]
    vr  = r["vol_ratio"]
    if pct >= 10 and vr >= SURGE_THRESHOLD:
        return "MISSED_UP"      # already pumped — too late to enter
    if pct <= -10 and vr >= SURGE_THRESHOLD:
        return "MISSED_DOWN"    # already dumped — too late to short
    if pct >= 3 and vr >= SURGE_THRESHOLD:
        return "BREAKOUT"       # strong up move + volume — investigate
    if pct <= -3 and vr >= SURGE_THRESHOLD:
        return "BREAKDOWN"      # strong down move + volume — avoid/short
    if vr >= SURGE_THRESHOLD:
        return "WATCH"          # volume spike without clear direction
    if pct >= 3:
        return "FLAT_VOL_UP"    # up move but no volume confirmation
    return "FLAT"


def _fmt_pick_rich(row, vol_info=None, freshness=None):
    """Format a stock pick using the weekly scan's rich format (same as
    telegram_notify.py:format_message).

    Args:
        row: pandas Series from the weekly scan CSV (has pattern, score,
             cmp, breakout, stop_loss, target_1, target_2, sector, etc.)
        vol_info: optional dict from daily scan with 'pct_chg' and 'vol_ratio'
                  to show today's volume action alongside the pattern setup.
        freshness: optional string like 'NEW' or 'Day 3' — shows how many
                   consecutive days this stock has appeared in the scan.
    """
    sym    = str(row["symbol"]).replace(".NS", "")
    pat    = str(row["pattern"])
    score  = row["score"]
    rr     = row["rr"]
    cmp    = row["cmp"]
    entry  = row["breakout"]
    stop   = row["stop_loss"]
    t1     = row.get("target_1", row.get("target", 0))
    t2     = row.get("target_2", t1)
    status = str(row.get("status", ""))
    sector = str(row.get("sector", ""))
    signal = str(row.get("sector_signal", ""))
    tf     = str(row.get("timeframe", "Daily"))

    pct_done   = row.get("pct_done", 0)
    pct_left   = row.get("pct_left", 100)
    upside_rem = row.get("upside_remaining", row.get("upside_%", 0))
    sustained      = str(row.get("sustained", "False")).lower() == "true"
    nested         = str(row.get("nested_cup", "False")).lower() == "true"
    double_confirm = str(row.get("double_confirm", "False")).lower() == "true"
    hist_resist    = row.get("hist_resist", "")

    sec_icon = {"BOOM": "🔥", "RISING": "↑", "COOLING": "↓", "WEAK": "🔴"}.get(signal, "")

    flag_parts = []
    if sustained:      flag_parts.append("[S]")
    if nested:         flag_parts.append("[N]")
    if double_confirm: flag_parts.append("[D]")
    flags = " ".join(flag_parts)

    resist_note = ""
    if hist_resist and str(hist_resist) not in ("", "nan", "0", "0.0"):
        try:
            resist_note = f"  ~prior resistance ₹{float(hist_resist):.0f}"
        except Exception:
            pass

    if status == "BREAKOUT":
        action = f"BUY NOW at ₹{cmp}"
    else:
        action = f"BUY above ₹{entry}"

    risk_pct = round((entry - stop) / entry * 100, 1) if entry > 0 else 0

    # Today's volume info (from daily scan) — shown as a bonus line
    vol_line = ""
    if vol_info:
        pct = vol_info.get("pct_chg", 0)
        vr  = vol_info.get("vol_ratio", 0)
        pct_str = ('+' if pct >= 0 else '') + str(pct) + '%'
        vol_line = f"   📊 Today: {pct_str}  ·  {vr}x vol"

    # Freshness badge: NEW (green) or Day N (shows repetition)
    fresh_badge = ""
    if freshness:
        if freshness == "NEW":
            fresh_badge = "  🆕 NEW"
        else:
            fresh_badge = f"  🔁 {freshness}"

    msg_lines = [
        "━━━━━━━━━━━━━━━━━━━",
        f"<b>{sym}</b>  Score {score}  {pat} [{tf}]  {flags}{fresh_badge}",
    ]
    if sector and sector not in ("", "Unknown", "nan"):
        msg_lines.append(f"   🏭 {sector} {sec_icon} {signal}")
    msg_lines.append(f"   💰 CMP ₹{cmp}  →  {action}")
    t2_str = f" → ₹{t2}" if t2 and t2 != t1 else ""
    msg_lines.append(f"   🛑 SL ₹{stop} ({risk_pct}% risk)  |  🎯 Target ₹{t1}{t2_str}")
    try:
        done_val = float(pct_done)
        left_val = float(pct_left)
        rem_val  = float(upside_rem)
        msg_lines.append(f"   📊 Move: {done_val:.0f}% done, {left_val:.0f}% left  |  +{rem_val:.1f}% to T2")
    except Exception:
        pass
    msg_lines.append(f"   📈 R:R 1:{rr}")
    if vol_line:
        msg_lines.append(vol_line)
    if resist_note:
        msg_lines.append(f"   ⚠️{resist_note}")

    return "\n".join(msg_lines)


def _fmt_pick(r, show_plan=True, pattern=None):
    """Format a daily-scan-only pick (not in weekly scan) — simpler format."""
    sym = _normalize_symbol(r["symbol"])
    pct = r["pct_chg"]
    pct_str = ('+' if pct >= 0 else '') + str(pct) + '%'
    vol_str = str(r['vol_ratio']) + 'x vol'
    pat_str = f"  ·  <i>{pattern}</i>" if pattern else ""

    if show_plan and "entry" in r and "stop" in r and "target" in r:
        rr = r.get("rr", 0)
        risk = r.get("risk_pct", 0)
        line1 = f"  ● <b>{sym}</b>  {pct_str}  ·  {vol_str}{pat_str}"
        line2 = (f"     → Entry <b>₹{r['entry']}</b>  |  SL <b>₹{r['stop']}</b>  |  "
                 f"Tgt <b>₹{r['target']}</b>")
        line3 = f"     → R:R <b>{rr}</b>  |  Risk <b>{risk}%</b>"
        return line1 + "\n" + line2 + "\n" + line3
    else:
        return f"  ● <b>{sym}</b>  {pct_str}  ·  {vol_str}{pat_str}  ·  CMP <b>₹{r['close']}</b>"


def _build_telegram_summary(args, hot_sectors, sector_perf, surges,
                            backbone_results, all_results,
                            sector_results, sector_syms):
    """Build a clean, actionable Telegram summary (SwingIQ format).

    Structure:
    1. Header + mode + sector heat
    2. Top weekly scan picks in rich format (Score, Pattern, Sector, CMP,
       SL, Target T1→T2, Move progress, R:R, flags) — these are the pattern
       setups being tracked for entry triggers. Today's volume info is
       appended if the stock appeared in today's daily scan.
    3. Today's volume movers (not in weekly scan) — simpler format
    4. Footer with flags legend
    """
    lines = []

    # Load full weekly scan DataFrame for rich formatting
    weekly_df, weekly_path = _load_weekly_scan_df()
    weekly_lookup = {}  # normalized_sym → DataFrame row
    if weekly_df is not None:
        for _, row in weekly_df.iterrows():
            sym = _normalize_symbol(str(row["symbol"]))
            weekly_lookup[sym] = row

    # Compute freshness: how many consecutive previous scans contained each pick
    freshness_map = {}
    if weekly_df is not None and weekly_path:
        try:
            current_syms = [_normalize_symbol(str(s)) for s in weekly_df["symbol"]]
            freshness_map = _compute_freshness(weekly_path, current_syms)
        except Exception as e:
            print(f"  [Freshness] Could not compute: {e}")

    # Build daily scan lookup: normalized symbol → vol_info dict
    daily_lookup = {}
    for r in all_results:
        sym = _normalize_symbol(r["symbol"])
        daily_lookup[sym] = {"pct_chg": r["pct_chg"], "vol_ratio": r["vol_ratio"]}

    # ── Mode line ──
    if args.bearish:
        lines.append("🔻 <b>Mode: BEARISH</b> (short candidates)")
    else:
        lines.append("📈 <b>Mode: BULLISH</b> (long candidates)")

    # ── Sector heat with actual % numbers ──
    if sector_perf:
        sec_map = {s: p for s, p, _ in sector_perf}
        sec_parts = []
        for s in hot_sectors:
            p = sec_map.get(s)
            if p is not None:
                sec_parts.append(f"<b>{s}</b> {'+' if p >= 0 else ''}{p}%")
            else:
                sec_parts.append(f"<b>{s}</b>")
        label = "Weak sectors" if args.bearish else "Hot sectors"
        lines.append(f"🔥 {label}: {', '.join(sec_parts)}")

    # ── Deduplicate all results by normalized symbol ──
    seen = set()
    deduped = []
    for r in all_results:
        key = _normalize_symbol(r["symbol"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # ── Categorize every stock with a volume surge ──
    surge_set = [r for r in deduped if r["vol_ratio"] >= SURGE_THRESHOLD]
    cats = {"BREAKOUT": [], "BREAKDOWN": [], "WATCH": [],
            "MISSED_UP": [], "MISSED_DOWN": [], "FLAT_VOL_UP": []}
    for r in surge_set:
        c = _categorize_pick(r)
        if c in cats:
            cats[c].append(r)

    # Sort each category by volume ratio (most volume first)
    for c in cats:
        cats[c].sort(key=lambda x: x["vol_ratio"], reverse=True)

    # ════════════════════════════════════════════════════════════════════
    # Section 1: Top weekly scan picks (rich format) — the pattern setups
    # ════════════════════════════════════════════════════════════════════
    if not args.bearish and weekly_df is not None and len(weekly_df) > 0:
        weekly_filtered = weekly_df
        if args.min_price or args.max_price:
            weekly_filtered = weekly_df[
                (args.min_price is None or weekly_df["cmp"] >= args.min_price) &
                (args.max_price is None or weekly_df["cmp"] <= args.max_price)
            ]
        top_weekly = weekly_filtered.head(10)
        if len(top_weekly) > 0:
            # Count NEW vs repeating for the header
            new_count = sum(1 for _, row in top_weekly.iterrows()
                           if freshness_map.get(_normalize_symbol(str(row["symbol"]))) == "NEW")
            repeat_count = len(top_weekly) - new_count
            fresh_summary = f" ({new_count} new, {repeat_count} repeating)" if freshness_map else ""
            lines.append(f"\n📋 <b>PATTERN SETUPS</b> — top {len(top_weekly)} from scan{fresh_summary}\n")
        for _, row in top_weekly.iterrows():
            sym = _normalize_symbol(str(row["symbol"]))
            vol_info = daily_lookup.get(sym)
            fresh_label = freshness_map.get(sym)
            lines.append(_fmt_pick_rich(row, vol_info=vol_info, freshness=fresh_label))

    # ════════════════════════════════════════════════════════════════════
    # Section 2: Today's volume movers (not in weekly scan)
    # ════════════════════════════════════════════════════════════════════
    # Filter out stocks already shown in the weekly scan section
    volume_only = [r for r in deduped
                   if _normalize_symbol(r["symbol"]) not in weekly_lookup
                   and r["vol_ratio"] >= SURGE_THRESHOLD]

    if args.bearish:
        weak_sector_stocks = set(_get_stocks_in_sectors(hot_sectors))
        bearish_picks = [r for r in all_results
                         if _normalize_symbol(r["symbol"]) in weak_sector_stocks
                         or r["symbol"] in weak_sector_stocks]
        bp_seen = set()
        bp_deduped = []
        for r in bearish_picks:
            k = _normalize_symbol(r["symbol"])
            if k not in bp_seen:
                bp_seen.add(k)
                bp_deduped.append(r)
        bearish_picks = bp_deduped
        bearish_picks.sort(key=lambda x: x["pct_chg"])

        shorts = [r for r in bearish_picks if r["pct_chg"] < -2 and r["vol_ratio"] > 1.5]
        watches = [r for r in bearish_picks if not (r["pct_chg"] < -2 and r["vol_ratio"] > 1.5)]

        if shorts:
            lines.append(f"\n🔻 <b>SHORT</b> — strong selling + volume ({len(shorts)})\n")
            for r in shorts[:5]:
                lines.append(_fmt_pick(r))
                lines.append("")
        if watches:
            lines.append(f"👀 <b>WATCH</b> — weak but no volume confirm ({len(watches)})\n")
            for r in watches[:5]:
                lines.append(_fmt_pick(r, show_plan=False))
        if not shorts and not watches:
            lines.append("\nNo bearish candidates in weak sectors today.")
    else:
        # Bullish volume movers not in weekly scan
        vol_breakout = [r for r in cats["BREAKOUT"]
                        if _normalize_symbol(r["symbol"]) not in weekly_lookup]
        vol_watch = [r for r in cats["WATCH"]
                     if _normalize_symbol(r["symbol"]) not in weekly_lookup]
        vol_breakdown = [r for r in cats["BREAKDOWN"]
                         if _normalize_symbol(r["symbol"]) not in weekly_lookup]

        if vol_breakout:
            lines.append(f"\n🟢 <b>VOLUME BREAKOUT</b> — today's surge ({len(vol_breakout)})\n")
            for r in vol_breakout[:5]:
                lines.append(_fmt_pick(r))
                lines.append("")
        if vol_watch:
            lines.append(f"👀 <b>VOLUME WATCH</b> — spike, no direction ({len(vol_watch)})\n")
            for r in vol_watch[:3]:
                lines.append(_fmt_pick(r))
        if vol_breakdown:
            lines.append(f"\n🔴 <b>BREAKDOWN</b> — avoid these ({len(vol_breakdown)})\n")
            for r in vol_breakdown[:3]:
                lines.append(_fmt_pick(r, show_plan=False))

        # Backbone movers (curated watchlist) — only those NOT in weekly scan
        bb_movers = [r for r in backbone_results
                     if (r["pct_chg"] >= 2 or r["vol_ratio"] >= SURGE_THRESHOLD)
                     and _normalize_symbol(r["symbol"]) not in weekly_lookup]
        bb_movers.sort(key=lambda x: x["vol_ratio"], reverse=True)
        bb_seen = set()
        bb_deduped = []
        for r in bb_movers:
            k = _normalize_symbol(r["symbol"])
            if k not in bb_seen:
                bb_seen.add(k)
                bb_deduped.append(r)
        if bb_deduped:
            lines.append(f"\n💼 <b>Backbone movers</b> ({len(bb_deduped)})\n")
            for r in bb_deduped[:5]:
                lines.append(_fmt_pick(r))
                lines.append("")

    # Footer with flags legend
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("<b>FLAGS:</b> [S]=Sustained  [N]=Nested cup  [D]=Double confirm")
    lines.append("⚠️ For research only. Not financial advice.")

    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sector",  type=str,  default=None, help="Force sector: METAL/AUTO/BANK/IT etc")
    parser.add_argument("--top",     type=int,  default=15)
    parser.add_argument("--sectors", type=int,  default=2,    help="Number of hot sectors to include")
    parser.add_argument("--min-price", type=float, default=None, help="Min stock price (e.g. 100)")
    parser.add_argument("--max-price", type=float, default=None, help="Max stock price (e.g. 400)")
    parser.add_argument("--bearish", action="store_true", help="Find weak sectors + short candidates")
    parser.add_argument("--no-notify", action="store_true", help="Skip Telegram notification")
    parser.add_argument("--env-file", type=str, default=None,
                        help="Which .env file to load Telegram creds from (e.g. .env.swingiq for prod bot)")
    parser.add_argument("--full", action="store_true",
                        help="Scan full NSE EQ universe (~2000+ stocks). Slower but catches everything.")
    parser.add_argument("--workers", type=int, default=8,
                        help="Number of parallel download threads (default 8)")
    args = parser.parse_args()

    today = date.today().strftime("%d-%b-%Y")
    print(f"\n{'='*70}")
    if args.bearish:
        print(f"  DAILY SCAN — BEARISH MODE  —  {today}")
    else:
        print(f"  DAILY MORNING SCAN v3  —  {today}")
    if args.min_price or args.max_price:
        print(f"  Price filter: {args.min_price or 0}-{args.max_price or 'inf'} Rs")
    print(f"{'='*70}")

    # Step 1: Sector heat map
    print("\n  Checking sector performance...")
    sector_perf = get_sector_performance()

    if sector_perf:
        print("\n  Sector Heat Map (today):")
        for s, pct, idx in sector_perf:
            if pct != pct:  # NaN check
                continue
            bar = "+" * int(abs(pct) * 2) if pct > 0 else "-" * int(abs(pct) * 2)
            sign = "UP  " if pct >= 0 else "DOWN"
            print(f"    {s:<10} {sign}  {('+' if pct>=0 else '')}{pct:>5.2f}%  {bar[:30]}")

    # Step 2: Pick sectors
    if args.bearish:
        # Bearish: pick WORST performing sectors (most selling pressure)
        if args.sector:
            hot_sectors = [args.sector.upper()]
        else:
            hot_sectors = [s for s, p, _ in sector_perf[-args.sectors:] if p < 0]
            if not hot_sectors and sector_perf:
                hot_sectors = [sector_perf[-1][0]]
        print(f"\n  Weak sectors today (most selling): {', '.join(hot_sectors)}")
    elif args.sector:
        hot_sectors = [args.sector.upper()]
        print(f"\n  Forced sector: {hot_sectors}")
    else:
        hot_sectors = [s for s, p, _ in sector_perf[:args.sectors] if p > 0]
        if not hot_sectors and sector_perf:
            hot_sectors = [sector_perf[0][0]]
        print(f"\n  Hot sectors today: {', '.join(hot_sectors)}")

    # Step 3: Build stock universe
    if args.full:
        # Full NSE EQ universe (~2000+ stocks)
        from data.nse_eq import fetch_nse_eq_universe
        print("\n  Loading full NSE EQ universe...")
        all_syms_ns = fetch_nse_eq_universe()
        all_syms = [s.replace(".NS", "") for s in all_syms_ns]
        print(f"\n  Universe: FULL NSE EQ = {len(all_syms)} stocks\n")
        # Scan in one batch
        all_results = run_scan(all_syms, "Full NSE EQ", workers=args.workers)
        backbone_results = [r for r in all_results if r["symbol"] in set(BACKBONE)]
        dynamic_results = [r for r in all_results if r["symbol"] not in set(BACKBONE)]
        sector_results = []
        sector_syms = []
    else:
        # Smart universe: Backbone + Nifty 500 + weekly picks + ALL stocks in hot sectors
        all_syms, breakdown = _build_smart_universe(
            hot_sectors, use_weekly_picks=True, use_nifty500=True
        )
        print(f"\n  Universe (SMART): {breakdown['backbone']} backbone + "
              f"{breakdown['weekly']} weekly picks + {breakdown['nifty500']} Nifty500 + "
              f"{breakdown['hot_sector']} hot sector stocks = {len(all_syms)} total\n")

        # Scan all at once with thread pool (faster than separate batches)
        all_results = run_scan(all_syms, "Smart universe", workers=args.workers)
        backbone_results = [r for r in all_results if r["symbol"] in set(BACKBONE)]
        dynamic_results = [r for r in all_results if r["symbol"] not in set(BACKBONE)]
        sector_results = []
        sector_syms = []

    # v3: Price filter
    if args.min_price or args.max_price:
        backbone_results = [r for r in backbone_results
                            if (args.min_price is None or r["close"] >= args.min_price) and
                               (args.max_price is None or r["close"] <= args.max_price)]
        dynamic_results = [r for r in dynamic_results
                           if (args.min_price is None or r["close"] >= args.min_price) and
                              (args.max_price is None or r["close"] <= args.max_price)]
        sector_results = [r for r in sector_results
                          if (args.min_price is None or r["close"] >= args.min_price) and
                             (args.max_price is None or r["close"] <= args.max_price)]
        print(f"  After price filter: {len(backbone_results)} backbone, {len(dynamic_results)} dynamic, {len(sector_results)} sector stocks")

    # Step 5: Print
    if args.bearish:
        # Bearish: show stocks with most selling (biggest negative % change)
        # Filter to stocks in weak sectors using our sector map
        weak_sector_stocks = set(_get_stocks_in_sectors(hot_sectors))
        all_sector = [r for r in all_results if r["symbol"] in weak_sector_stocks]
        all_sector.sort(key=lambda x: x["pct_chg"])  # worst first
        print(f"\n{'='*70}")
        print(f"  BEARISH CANDIDATES — Most Selling in Weak Sectors")
        print(f"{'='*70}")
        print(f"  {'Stock':<14} {'Close':>8} {'Chg%':>7} {'Vol(L)':>8} {'VolRatio':>9}  Signal")
        print(f"  {'-'*60}")
        for r in all_sector[:args.top]:
            chg_str = str(r['pct_chg']) + '%'
            signal = "SHORT" if r['pct_chg'] < -2 and r['vol_ratio'] > 1.5 else "WATCH"
            print(f"  {r['symbol']:<14} {r['close']:>8.2f} {chg_str:>7} {r['cur_vol']:>8.1f} {str(r['vol_ratio'])+'x':>9}  {signal}")
    else:
        print_results(backbone_results, "BACKBONE 50 — Volume & Movers", top=args.top)

        # Show all non-backbone results
        if dynamic_results:
            print_results(dynamic_results, "ALL SCANNED STOCKS — Volume & Movers", top=args.top)

        # Show hot sector stocks specifically
        for sec in hot_sectors:
            sec_stocks = set(_get_stocks_in_sectors([sec]))
            sec_res = [r for r in all_results if r["symbol"] in sec_stocks]
            print_results(sec_res, f"HOT SECTOR — {sec} ({len(sec_res)} stocks)", top=args.top)

        # Step 6: Top picks across ALL sources
        all_results_combined = backbone_results + dynamic_results + sector_results
        # Deduplicate by symbol (use filtered lists, not raw all_results)
        seen_syms = set()
        deduped = []
        for r in all_results_combined:
            if r["symbol"] not in seen_syms:
                seen_syms.add(r["symbol"])
                deduped.append(r)
        all_results = deduped

        surges = [r for r in all_results if r["vol_ratio"] >= SURGE_THRESHOLD]
        surges.sort(key=lambda x: x["vol_ratio"], reverse=True)

        if surges:
            print(f"\n{'='*70}")
            print(f"  TOP VOLUME SURGE PICKS TODAY ({len(surges)} stocks)")
            print(f"{'='*70}")
            for r in surges[:10]:
                print(f"  {r['symbol']:<14}  {r['vol_ratio']}x vol  |  {('+' if r['pct_chg']>=0 else '')}{r['pct_chg']}%  |  CMP {r['close']}")
        else:
            print(f"\n  No significant volume surges today (threshold: {SURGE_THRESHOLD}x)")

    print()

    # Auto-send daily summary to Telegram (unless --no-notify)
    if not args.no_notify:
        header = f"📊 SwingIQ Daily Scan — {date.today().strftime('%d %b %Y')}"
        lines = _build_telegram_summary(
            args, hot_sectors, sector_perf, surges, backbone_results,
            all_results, sector_results, sector_syms
        )
        send_daily_summary("\n".join(lines), header=header, env_file=args.env_file)
        print()


if __name__ == "__main__":
    main()
