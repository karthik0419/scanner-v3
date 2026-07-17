"""
Sector Rotation Engine v3 — Self-contained (no external dependency).

Based on scanner/utils/sector_rotation.py but enhanced:
  - BOOM/RISING/COOLING/WEAK signals (same as v2)
  - Bearish mode: identifies WEAK sectors for short setups
  - NSE Heat Map integration: finds sectors with most selling pressure
  - Authoritative stock→sector mapping from NSE official index constituents
  - Fallback to yfinance .info `industry` field for unknown stocks
"""
import warnings
warnings.filterwarnings("ignore")
import os, json
import yfinance as yf
import pandas as pd

# NSE Sector indices on yfinance
SECTOR_INDICES = {
    'Banking':       '^NSEBANK',
    'IT':            '^CNXIT',
    'Pharma':        '^CNXPHARMA',
    'Auto':          '^CNXAUTO',
    'Metals':        '^CNXMETAL',
    'FMCG':          '^CNXFMCG',
    'Infra':         '^CNXINFRA',
    'Realty':        '^CNXREALTY',
    'Energy':        '^CNXENERGY',
    'Media':         '^CNXMEDIA',
    'MidCap':        '^NSEMDCP50',
    'PSU Bank':      '^CNXPSUBANK',
}

# Load authoritative NSE sector mapping (built by utils/build_sector_map.py)
_NSE_SECTORS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "nse_sectors.json")
_NSE_SECTORS_PATH = os.path.abspath(_NSE_SECTORS_PATH)
STOCK_SECTOR = {}  # Loaded from JSON at module init

def _load_nse_sectors():
    """Load NSE official sector mapping from JSON file."""
    global STOCK_SECTOR
    try:
        with open(_NSE_SECTORS_PATH) as f:
            raw = json.load(f)
        # Store with .NS suffix for consistency with scanner symbols
        STOCK_SECTOR = {f"{sym}.NS": sector for sym, sector in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # Will fall back to yfinance

_load_nse_sectors()

# yfinance `industry` field -> Scanner Sector (granular fallback)
YF_INDUSTRY_TO_SECTOR = {
    'Banks - Regional':                      'Banking',
    'Banks - Diversified':                   'Banking',
    'Capital Markets':                       'Banking',
    'Credit Services':                       'Banking',
    'Asset Management':                      'Banking',
    'Insurance - Diversified':               'Banking',
    'Insurance - Life':                      'Banking',
    'Financial Data & Stock Exchanges':      'Banking',
    'Financial Conglomerates':               'Banking',
    'Information Technology Services':       'IT',
    'Software - Infrastructure':             'IT',
    'Software - Application':                'IT',
    'Software - Services':                   'IT',
    'Communication Equipment':               'Telecom',
    'Electronic Components':                 'IT',
    'Semiconductors':                        'IT',
    'Computer Hardware':                     'IT',
    'Electronics & Computer Distribution':   'IT',
    'Drug Manufacturers - General':          'Pharma',
    'Drug Manufacturers - Specialty & Generic': 'Pharma',
    'Biotechnology':                         'Pharma',
    'Medical Devices':                       'Pharma',
    'Healthcare Information Services':        'Pharma',
    'Medical Care Facilities':               'Pharma',
    'Medical Instruments & Supplies':        'Pharma',
    'Diagnostics & Research':                'Pharma',
    'Auto Manufacturers':                    'Auto',
    'Auto Parts':                            'Auto',
    'Auto Parts & Equipment':                'Auto',
    'Rubber & Tires':                        'Auto',
    'Recreational Vehicles':                 'Auto',
    'Trucking':                              'Auto',
    'Steel':                                 'Metals',
    'Aluminum':                              'Metals',
    'Copper':                                'Metals',
    'Other Industrial Metals & Mining':      'Metals',
    'Gold':                                  'Metals',
    'Silver':                                'Metals',
    'Other Precious Metals & Mining':        'Metals',
    'Metal Fabrication':                     'Metals',
    'Oil & Gas E&P':                         'Energy',
    'Oil & Gas Integrated':                  'Energy',
    'Oil & Gas Midstream':                   'Energy',
    'Oil & Gas Refining & Marketing':        'Energy',
    'Oil & Gas Equipment & Services':        'Energy',
    'Utilities - Regulated Electric':        'Energy',
    'Utilities - Regulated Gas':             'Energy',
    'Utilities - Renewable':                 'Energy',
    'Solar':                                 'Energy',
    'Wind':                                  'Energy',
    'Utilities - Diversified':               'Energy',
    'Utilities - Independent Power Producers': 'Energy',
    'Packaged Foods':                        'FMCG',
    'Beverages - Non-Alcoholic':             'FMCG',
    'Beverages - Brewers':                   'FMCG',
    'Beverages - Wineries & Distilleries':    'FMCG',
    'Confectioners':                         'FMCG',
    'Farm Products':                         'FMCG',
    'Household & Personal Products':         'FMCG',
    'Personal Services':                     'FMCG',
    'Tobacco':                               'FMCG',
    'Engineering - Construction':            'Infra',
    'Infrastructure Operations':             'Infra',
    'Building Materials':                    'Infra',
    'Cement':                                'Infra',
    'Specialty Industrial Machinery':        'Infra',
    'General Industrial Machinery':          'Infra',
    'Electrical Equipment & Parts':          'Infra',
    'Heavy Machinery':                       'Infra',
    'Industrial Distribution':               'Infra',
    'Rental & Leasing Services':             'Infra',
    'Aerospace & Defense':                   'Infra',
    'Specialty Business Services':           'Infra',
    'Real Estate - Development':             'Realty',
    'Real Estate Services':                  'Realty',
    'Real Estate - Diversified':             'Realty',
    'REITs':                                 'Realty',
    'Broadcasting':                          'Media',
    'Entertainment':                         'Media',
    'Media - Diversified':                   'Media',
    'Advertising Agencies':                  'Media',
    'Publishing':                            'Media',
    'Advertising & Marketing Services':      'Media',
    'Telecom Services':                      'Telecom',
    'Wireless Communication':                'Telecom',
    'Textile Manufacturing':                 'Textiles',
    'Apparel Manufacturing':                 'Textiles',
    'Apparel Retail':                        'Textiles',
    'Footwear & Accessories':                'Textiles',
    'Specialty Chemicals':                   'Chemicals',
    'Agricultural Inputs':                   'Chemicals',
    'Chemicals':                             'Chemicals',
    'Fertilizers':                           'Chemicals',
    'Pesticides':                            'Chemicals',
    'Furnishings, Fixtures & Appliances':    'Consumer Durables',
    'Consumer Electronics':                  'Consumer Durables',
    'Luxury Goods':                          'Consumer Durables',
    'Restaurants':                           'Services',
    'Travel Services':                       'Services',
    'Specialty Retail':                      'Services',
    'Department Stores':                     'Services',
    'Internet Retail':                       'Services',
    'Discount Stores':                       'Services',
    'Conglomerates':                         'Diversified',
}

# Legacy yfinance `sector` field -> Scanner Sector (coarse, last resort)
YF_SECTOR_MAP = {
    'Basic Materials':          'Metals',
    'Consumer Cyclical':        'Auto',
    'Consumer Defensive':       'FMCG',
    'Energy':                   'Energy',
    'Financial Services':       'Banking',
    'Healthcare':               'Pharma',
    'Industrials':              'Infra',
    'Real Estate':              'Realty',
    'Technology':               'IT',
    'Communication Services':   'Media',
    'Utilities':                'Energy',
}

_cache = {}
_sector_lookup_cache = {}


def get_sector_heat(lookback_short=5, lookback_long=20):
    """
    Returns dict: sector -> {'perf_5d', 'perf_20d', 'signal', 'score_bonus'}
    signal: BOOM / RISING / COOLING / WEAK
    score_bonus: +20 BOOM, +10 RISING, 0 COOLING, -10 WEAK
    Cached for the session.
    """
    global _cache
    if _cache:
        return _cache

    heat = {}
    for sector, ticker in SECTOR_INDICES.items():
        try:
            df = yf.download(ticker, period='3mo', interval='1d',
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) < lookback_long + 2:
                continue

            curr   = float(df['Close'].iloc[-1])
            p5     = float(df['Close'].iloc[-(lookback_short+1)])
            p20    = float(df['Close'].iloc[-(lookback_long+1)])

            perf_5d  = round((curr - p5)  / p5  * 100, 2)
            perf_20d = round((curr - p20) / p20 * 100, 2)

            if perf_5d > 2 and perf_20d > 3:
                signal, bonus = 'BOOM',    20
            elif perf_5d > 0 and perf_20d > 0:
                signal, bonus = 'RISING',  10
            elif perf_5d < 0 and perf_20d > 0:
                signal, bonus = 'COOLING',  0
            else:
                signal, bonus = 'WEAK',   -10

            heat[sector] = {
                'perf_5d':  perf_5d,
                'perf_20d': perf_20d,
                'signal':   signal,
                'bonus':    bonus,
            }
        except Exception:
            pass

    _cache = heat
    return heat


def get_stock_sector(symbol):
    """Return sector name.

    Lookup priority:
      1. NSE official sector map (data/nse_sectors.json — 568+ stocks)
      2. Session cache (from previous yfinance lookups)
      3. yfinance `industry` field (granular — e.g. "Textile Manufacturing")
      4. yfinance `sector` field (coarse — e.g. "Consumer Cyclical")
      5. 'Unknown'
    """
    global _sector_lookup_cache
    sym_ns  = symbol if symbol.endswith('.NS') else symbol + '.NS'
    sym_raw = symbol.replace('.NS','')

    # 1. NSE official sector map (instant — loaded from JSON at module init)
    sec = STOCK_SECTOR.get(sym_ns) or STOCK_SECTOR.get(sym_raw)
    if sec:
        return sec

    # 2. Session cache
    if sym_ns in _sector_lookup_cache:
        return _sector_lookup_cache[sym_ns]

    # 3. yfinance `industry` field (granular fallback)
    try:
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            info = yf.Ticker(sym_ns).info
        # Try industry first (more granular)
        yf_industry = info.get('industry', '')
        if yf_industry:
            mapped = YF_INDUSTRY_TO_SECTOR.get(yf_industry)
            if mapped:
                _sector_lookup_cache[sym_ns] = mapped
                return mapped
        # Fall back to coarse sector
        yf_sector = info.get('sector', '')
        mapped = YF_SECTOR_MAP.get(yf_sector, yf_sector or 'Unknown')
        _sector_lookup_cache[sym_ns] = mapped
        return mapped
    except Exception:
        _sector_lookup_cache[sym_ns] = 'Unknown'
        return 'Unknown'


def get_sector_bonus(symbol):
    """
    Returns (sector, signal, score_bonus) for a symbol.
    Used by scanner.py to boost/penalise score.
    """
    heat   = get_sector_heat()
    sector = get_stock_sector(symbol)
    if sector == 'Unknown' or sector not in heat:
        return sector, 'Unknown', 0
    h = heat[sector]
    return sector, h['signal'], h['bonus']


def get_weak_sectors():
    """Return list of (sector, perf_5d, perf_20d) for WEAK sectors — for bearish scans."""
    heat = get_sector_heat()
    weak = [(s, h['perf_5d'], h['perf_20d'])
            for s, h in heat.items() if h['signal'] == 'WEAK']
    return sorted(weak, key=lambda x: x[1])


def get_hot_sectors(top_n=3):
    """Return list of (sector, perf_5d, perf_20d) for top-performing sectors."""
    heat = get_sector_heat()
    hot = [(s, h['perf_5d'], h['perf_20d'])
           for s, h in heat.items() if h['signal'] in ('BOOM', 'RISING')]
    return sorted(hot, key=lambda x: x[1], reverse=True)[:top_n]


def print_sector_heatmap():
    """Print current sector rotation heatmap."""
    heat = get_sector_heat()
    rows = sorted(heat.items(), key=lambda x: x[1]['perf_5d'], reverse=True)
    print('\n  SECTOR ROTATION HEATMAP')
    print(f'  {"Sector":<16} {"5D":>7} {"20D":>7}  Signal')
    print('  ' + '-'*48)
    for s, h in rows:
        icon = '[+]' if h['signal']=='BOOM' else '[>]' if h['signal']=='RISING' else '[<]' if h['signal']=='COOLING' else '[-]'
        print(f'  {s:<16} {h["perf_5d"]:>+6.2f}%  {h["perf_20d"]:>+6.2f}%  {icon} {h["signal"]}')
    print()


if __name__ == '__main__':
    print_sector_heatmap()
    print("\n  Weak sectors (for bearish scans):")
    for s, p5, p20 in get_weak_sectors():
        print(f"    {s:<16} 5d={p5:+.2f}%  20d={p20:+.2f}%")
