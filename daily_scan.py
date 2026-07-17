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
    """Returns list of (sector, pct_change_today) sorted best first."""
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
    """Fetch last close, volume, 20d avg volume."""
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
        return {
            "symbol":    symbol,
            "close":     round(cur_close, 2),
            "pct_chg":   pct_chg,
            "vol_ratio": vol_ratio,
            "avg_vol":   round(avg_vol / 1e5, 1),   # in lakhs
            "cur_vol":   round(cur_vol / 1e5, 1),
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sector",  type=str,  default=None, help="Force sector: METAL/AUTO/BANK/IT etc")
    parser.add_argument("--top",     type=int,  default=15)
    parser.add_argument("--sectors", type=int,  default=2,    help="Number of hot sectors to include")
    parser.add_argument("--min-price", type=float, default=None, help="Min stock price (e.g. 100)")
    parser.add_argument("--max-price", type=float, default=None, help="Max stock price (e.g. 400)")
    parser.add_argument("--bearish", action="store_true", help="Find weak sectors + short candidates")
    parser.add_argument("--no-notify", action="store_true", help="Skip Telegram notification")
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
        all_results_combined = backbone_results + dynamic_results
        # Deduplicate by symbol
        seen_syms = set()
        deduped = []
        for r in all_results:
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
        header = f"📊 DAILY SCAN — {date.today().strftime('%d %b %Y')}"
        lines = []
        if args.bearish:
            lines.append("🔻 Mode: BEARISH (short candidates)")
            lines.append(f"Weak sectors: {', '.join(hot_sectors)}")
            bearish_picks = [r for r in sector_results if r["symbol"] in sector_syms]
            bearish_picks.sort(key=lambda x: x["pct_chg"])
            for r in bearish_picks[:5]:
                lines.append(f"  {r['symbol']} | {r['pct_chg']}% | vol {r['vol_ratio']}x | CMP {r['close']}")
        else:
            lines.append(f"🔥 Hot sectors: {', '.join(hot_sectors)}")
            if surges:
                lines.append(f"\n📈 Top volume surges ({len(surges)}):")
                for r in surges[:5]:
                    lines.append(f"  {r['symbol']} | {r['vol_ratio']}x vol | {('+' if r['pct_chg']>=0 else '')}{r['pct_chg']}% | CMP {r['close']}")
            else:
                lines.append("\nNo significant volume surges today.")
            # Top backbone movers
            top_movers = [r for r in backbone_results if r["pct_chg"] >= 2 or r["vol_ratio"] >= SURGE_THRESHOLD]
            top_movers.sort(key=lambda x: x["vol_ratio"], reverse=True)
            if top_movers:
                lines.append(f"\n💼 Top backbone movers:")
                for r in top_movers[:5]:
                    lines.append(f"  {r['symbol']} | {('+' if r['pct_chg']>=0 else '')}{r['pct_chg']}% | {r['vol_ratio']}x vol | CMP {r['close']}")
        lines.append("\n⚠️ For research only. Not financial advice.")
        send_daily_summary("\n".join(lines), header=header)
        print()


if __name__ == "__main__":
    main()
