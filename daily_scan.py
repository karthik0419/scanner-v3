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


def run_scan(symbols, label=""):
    results = []
    total = len(symbols)
    for i, sym in enumerate(symbols):
        print(f"  [{i+1}/{total}] {sym:<15}", end="\r")
        info = get_price_info(sym)
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
    sector_syms = []
    for sec in hot_sectors:
        sector_syms += SECTOR_STOCKS.get(sec, [])
    sector_syms = list(dict.fromkeys(sector_syms))

    all_syms = list(dict.fromkeys(BACKBONE + sector_syms))
    print(f"\n  Scanning {len(BACKBONE)} backbone + {len(sector_syms)} sector stocks = {len(all_syms)} total\n")

    # Step 4: Scan
    backbone_results = run_scan(BACKBONE, "Backbone")
    sector_results   = run_scan(sector_syms, "Sector")

    # v3: Price filter
    if args.min_price or args.max_price:
        backbone_results = [r for r in backbone_results
                            if (args.min_price is None or r["close"] >= args.min_price) and
                               (args.max_price is None or r["close"] <= args.max_price)]
        sector_results = [r for r in sector_results
                          if (args.min_price is None or r["close"] >= args.min_price) and
                             (args.max_price is None or r["close"] <= args.max_price)]
        print(f"  After price filter: {len(backbone_results)} backbone, {len(sector_results)} sector stocks")

    # Step 5: Print
    if args.bearish:
        # Bearish: show stocks with most selling (biggest negative % change)
        all_sector = [r for r in sector_results if r["symbol"] in sector_syms]
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

        for sec in hot_sectors:
            sec_syms = SECTOR_STOCKS.get(sec, [])
            sec_res  = [r for r in sector_results if r["symbol"] in sec_syms]
            print_results(sec_res, f"HOT SECTOR — {sec}", top=args.top)

        # Step 6: Top picks across all
        all_results = backbone_results + [r for r in sector_results if r["symbol"] not in BACKBONE]
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


if __name__ == "__main__":
    main()
