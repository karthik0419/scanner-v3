"""
Build authoritative stock→sector mapping from NSE official index constituents.

Downloads constituent lists from NSE archives (which include an 'Industry' column),
merges them, and maps NSE industries to our scanner sector names.

For stocks not in any NSE index (small-caps), falls back to yfinance's `industry`
field (more granular than `sector`) and maps it to our scanner sectors.

Output: data/nse_sectors.json  (symbol -> sector)
        data/nse_industries.json (symbol -> NSE/yfinance industry, for reference)
"""
import os, sys, csv, io, json, requests
from collections import defaultdict

HEADERS = {'User-Agent': 'Mozilla/5.0'}
BASE = 'https://archives.nseindia.com/content/indices/ind_{}list.csv'

# NSE sectoral indices to download (specific sectors take priority over broad indices)
SECTORAL_INDICES = {
    'niftyauto':              'Auto',
    'niftybank':              'Banking',
    'niftyfmcg':              'FMCG',
    'niftyit':                'IT',
    'niftymedia':             'Media',
    'niftymetal':             'Metals',
    'niftypharma':            'Pharma',
    'niftyrealty':            'Realty',
    'niftypsubank':           'PSU Bank',
    'niftyenergy':            'Energy',
    'niftyinfra':             'Infra',
    'niftyoilgas':            'Energy',
    'niftyconsumerdurables':  'Consumer Durables',
    'niftyhealthcare':        'Healthcare',
}

# Broad indices (lower priority — only used if stock not in any sectoral index)
BROAD_INDICES = ['nifty500', 'nifty200', 'nifty100', 'nifty50']

# NSE Industry -> Scanner Sector mapping
# (used for stocks that only appear in broad indices, not sectoral ones)
NSE_INDUSTRY_TO_SECTOR = {
    'Financial Services':                    'Banking',
    'Capital Goods':                         'Infra',
    'Healthcare':                            'Pharma',
    'Automobile and Auto Components':        'Auto',
    'Consumer Services':                     'Services',
    'Fast Moving Consumer Goods':            'FMCG',
    'Information Technology':                'IT',
    'Chemicals':                             'Chemicals',
    'Metals & Mining':                       'Metals',
    'Power':                                 'Energy',
    'Oil Gas & Consumable Fuels':            'Energy',
    'Consumer Durables':                     'Consumer Durables',
    'Services':                              'Services',
    'Construction':                          'Infra',
    'Construction Materials':                'Infra',
    'Realty':                                'Realty',
    'Telecommunication':                     'Telecom',
    'Textiles':                              'Textiles',
    'Media Entertainment & Publication':     'Media',
    'Diversified':                           'Diversified',
}

# yfinance `industry` field -> Scanner Sector mapping
# (used for stocks not in any NSE index — small/micro caps)
# More granular than yfinance `sector` field.
YF_INDUSTRY_TO_SECTOR = {
    # Banking / Financial
    'Banks - Regional':                      'Banking',
    'Banks - Diversified':                   'Banking',
    'Capital Markets':                       'Banking',
    'Credit Services':                       'Banking',
    'Asset Management':                      'Banking',
    'Insurance - Diversified':               'Banking',
    'Insurance - Life':                      'Banking',
    'Financial Data & Stock Exchanges':      'Banking',
    'Financial Conglomerates':               'Banking',
    # IT
    'Information Technology Services':       'IT',
    'Software - Infrastructure':             'IT',
    'Software - Application':                'IT',
    'Software - Services':                   'IT',
    'Communication Equipment':               'Telecom',
    'Electronic Components':                 'IT',
    'Semiconductors':                        'IT',
    'Computer Hardware':                     'IT',
    'Electronics & Computer Distribution':   'IT',
    # Pharma / Healthcare
    'Drug Manufacturers - General':          'Pharma',
    'Drug Manufacturers - Specialty & Generic': 'Pharma',
    'Biotechnology':                         'Pharma',
    'Medical Devices':                       'Pharma',
    'Healthcare Information Services':        'Pharma',
    'Medical Care Facilities':               'Pharma',
    'Medical Instruments & Supplies':        'Pharma',
    'Diagnostics & Research':                'Pharma',
    # Auto
    'Auto Manufacturers':                    'Auto',
    'Auto Parts':                            'Auto',
    'Auto Parts & Equipment':                'Auto',
    'Rubber & Tires':                        'Auto',
    'Recreational Vehicles':                 'Auto',
    'Trucking':                              'Auto',
    # Metals
    'Steel':                                 'Metals',
    'Aluminum':                              'Metals',
    'Copper':                                'Metals',
    'Other Industrial Metals & Mining':      'Metals',
    'Gold':                                  'Metals',
    'Silver':                                'Metals',
    'Other Precious Metals & Mining':        'Metals',
    'Metal Fabrication':                     'Metals',
    # Energy
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
    # FMCG
    'Packaged Foods':                        'FMCG',
    'Beverages - Non-Alcoholic':             'FMCG',
    'Beverages - Brewers':                   'FMCG',
    'Beverages - Wineries & Distilleries':    'FMCG',
    'Confectioners':                         'FMCG',
    'Farm Products':                         'FMCG',
    'Household & Personal Products':         'FMCG',
    'Personal Services':                     'FMCG',
    'Tobacco':                               'FMCG',
    # Infra / Capital Goods / Construction
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
    # Realty
    'Real Estate - Development':             'Realty',
    'Real Estate Services':                  'Realty',
    'Real Estate - Diversified':             'Realty',
    'REITs':                                 'Realty',
    # Media
    'Broadcasting':                          'Media',
    'Entertainment':                         'Media',
    'Media - Diversified':                   'Media',
    'Advertising Agencies':                  'Media',
    'Publishing':                            'Media',
    'Advertising & Marketing Services':      'Media',
    # Telecom
    'Telecom Services':                      'Telecom',
    'Wireless Communication':                'Telecom',
    # Textiles
    'Textile Manufacturing':                 'Textiles',
    'Apparel Manufacturing':                 'Textiles',
    'Apparel Retail':                        'Textiles',
    'Footwear & Accessories':                'Textiles',
    # Chemicals
    'Specialty Chemicals':                   'Chemicals',
    'Agricultural Inputs':                   'Chemicals',
    'Chemicals':                             'Chemicals',
    'Fertilizers':                           'Chemicals',
    'Pesticides':                            'Chemicals',
    # Consumer Durables / Services
    'Furnishings, Fixtures & Appliances':    'Consumer Durables',
    'Consumer Electronics':                  'Consumer Durables',
    'Luxury Goods':                          'Consumer Durables',
    'Restaurants':                           'Services',
    'Travel Services':                       'Services',
    'Personal Services':                     'Services',
    'Specialty Retail':                      'Services',
    'Department Stores':                     'Services',
    'Internet Retail':                       'Services',
    'Discount Stores':                       'Services',
    # Diversified
    'Conglomerates':                         'Diversified',
}

# Stocks where yfinance is known to be wrong — manual overrides
# (symbol without .NS -> correct sector)
MANUAL_OVERRIDES = {
    'ZAGGLE':    'Banking',    # Fintech/payments — yfinance says Software, but trades with financials
    'KAYNES':    'IT',         # Electronic manufacturing services — NSE says Capital Goods, but it's tech
}


def download_index(slug):
    """Download NSE index constituent CSV. Returns list of (symbol, industry) tuples."""
    url = BASE.format(slug)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if not r.ok or len(r.text) < 100:
            return []
        reader = csv.DictReader(io.StringIO(r.text))
        stocks = []
        for row in reader:
            sym = row.get('Symbol', '').strip().upper()
            ind = row.get('Industry', '').strip()
            if sym:
                stocks.append((sym, ind))
        return stocks
    except Exception:
        return []


def build_sector_map(extra_symbols=None):
    """Build symbol -> sector mapping from NSE official data + yfinance fallback.

    Args:
        extra_symbols: list of symbols (without .NS) to ensure are mapped via yfinance
                       if not in any NSE index. Used to pre-populate small-caps.
    """
    sector_map = {}  # symbol -> sector
    symbol_industries = {}  # symbol -> NSE industry (for fallback)

    # 1. Download sectoral indices first (these are authoritative)
    print("Downloading sectoral indices...")
    for slug, sector in SECTORAL_INDICES.items():
        stocks = download_index(slug)
        print(f"  {slug:<35} {len(stocks):>4} stocks -> {sector}")
        for sym, ind in stocks:
            sector_map[sym] = sector
            if ind:
                symbol_industries[sym] = ind

    # 2. Download broad indices for stocks not in any sectoral index
    print("\nDownloading broad indices (for remaining stocks)...")
    for slug in BROAD_INDICES:
        stocks = download_index(slug)
        print(f"  {slug:<35} {len(stocks):>4} stocks")
        for sym, ind in stocks:
            if sym not in sector_map:
                # Map via NSE industry classification
                sector = NSE_INDUSTRY_TO_SECTOR.get(ind, '')
                if sector:
                    sector_map[sym] = sector
                if ind:
                    symbol_industries[sym] = ind

    # 3. Apply manual overrides (highest priority)
    for sym, sector in MANUAL_OVERRIDES.items():
        sector_map[sym] = sector
        print(f"  Override: {sym} -> {sector}")

    # 4. yfinance industry fallback for extra symbols not in any NSE index
    if extra_symbols:
        unmapped = [s for s in extra_symbols if s not in sector_map]
        if unmapped:
            print(f"\nFetching yfinance industry for {len(unmapped)} unmapped stocks...")
            import yfinance as yf
            mapped = 0
            for sym in unmapped:
                try:
                    info = yf.Ticker(sym + '.NS').info
                    industry = info.get('industry', '')
                    if industry:
                        sector = YF_INDUSTRY_TO_SECTOR.get(industry, '')
                        if sector:
                            sector_map[sym] = sector
                            symbol_industries[sym] = f"yf: {industry}"
                            mapped += 1
                        else:
                            # Try yfinance sector as last resort
                            yf_sector = info.get('sector', '')
                            sector = YF_SECTOR_MAP_LEGACY.get(yf_sector, '')
                            if sector:
                                sector_map[sym] = sector
                                symbol_industries[sym] = f"yf_sector: {yf_sector}"
                                mapped += 1
                            else:
                                symbol_industries[sym] = f"yf_unmapped: {industry}"
                except Exception:
                    pass
            print(f"  Mapped {mapped}/{len(unmapped)} via yfinance industry")

    # 5. Report coverage
    print(f"\n{'='*60}")
    print(f"  SECTOR MAP SUMMARY")
    print(f"{'='*60}")
    print(f"  Total stocks mapped: {len(sector_map)}")

    # Count by sector
    from collections import Counter
    sector_counts = Counter(sector_map.values())
    print(f"\n  By sector:")
    for sec, count in sector_counts.most_common():
        print(f"    {sec:<25} {count:>4}")

    # Unmapped industries (stocks in broad indices with no sectoral mapping)
    unmapped_inds = set()
    for sym, ind in symbol_industries.items():
        if sym not in sector_map and ind:
            unmapped_inds.add(ind)
    if unmapped_inds:
        print(f"\n  Unmapped NSE industries: {unmapped_inds}")

    return sector_map, symbol_industries


# Legacy yfinance sector → scanner sector (coarse, only used as last resort)
YF_SECTOR_MAP_LEGACY = {
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


def verify_picks(sector_map, symbol_industries):
    """Verify today's scan picks against the new mapping."""
    print(f"\n{'='*60}")
    print(f"  VERIFICATION — Today's scan picks")
    print(f"{'='*60}")
    test_picks = [
        ('NATCOPHARM', 'Pharma'),
        ('STCINDIA', 'Trading'),       # was wrongly Infra
        ('IDBI', 'Banking'),
        ('GTLINFRA', 'Infra'),         # was wrongly IT
        ('PRAENG', 'Realty'),
        ('NETWORK18', 'Media'),
        ('ENIL', 'Media'),
        ('BCG', 'Media'),
        ('BIRLAMONEY', 'Banking'),
        ('SURAJEST', 'Realty'),
        ('ZAGGLE', 'Banking'),         # was wrongly IT
        ('MCLOUD', 'FMCG'),            # was wrongly IT (tea company!)
        ('RBA', 'Auto'),
        ('URJA', 'Energy'),            # was wrongly IT
        ('FEDFINA', 'Banking'),
        ('DHANBANK', 'Banking'),
        ('SUNTECK', 'Realty'),
        ('BFINVEST', 'Banking'),
        ('EMKAY', 'Banking'),
        ('KAYNES', 'IT'),
        ('KSCL', 'Metals'),
        ('ACL', 'Auto'),               # was wrongly Metals (auto glass)
        ('PNGJL', 'Consumer'),
        ('YATRA', 'Services'),         # was wrongly Auto (travel company)
        ('ALOKINDS', 'Textiles'),      # was wrongly Auto
        ('NILKAMAL', 'Consumer'),      # was wrongly Auto (plastic furniture)
        ('ALICON', 'Auto'),            # was wrongly Infra (auto components)
        ('VARDMNPOLY', 'Textiles'),    # was wrongly Auto
        ('SALONA', 'Textiles'),
        ('RHIM', 'Infra'),
    ]
    correct = 0
    wrong = 0
    not_found = 0
    for sym, expected in test_picks:
        new_sector = sector_map.get(sym)
        nse_ind = symbol_industries.get(sym, '')
        if new_sector is None:
            status = 'NOT FOUND'
            not_found += 1
        elif expected.lower() in new_sector.lower() or new_sector.lower() in expected.lower():
            status = 'OK'
            correct += 1
        else:
            status = f'WRONG (expected {expected})'
            wrong += 1
        print(f"  {sym:<15} NSE industry: {nse_ind:<35} -> {new_sector or 'N/A':<20} {status}")

    print(f"\n  Correct: {correct} | Wrong: {wrong} | Not found: {not_found} | Total: {len(test_picks)}")


def main():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Load today's scan picks + backbone50 + nifty200 to ensure full coverage
    extra_symbols = set()
    results_dir = os.path.join(os.path.dirname(output_dir), "results")
    # Today's scan picks
    import glob
    for csv in glob.glob(os.path.join(results_dir, "v3_*.csv")):
        if "_all" not in csv:
            try:
                import pandas as pd
                df = pd.read_csv(csv)
                for sym in df["symbol"]:
                    extra_symbols.add(sym.replace(".NS", ""))
            except Exception:
                pass
    # Backbone50
    backbone_path = os.path.join(os.path.dirname(output_dir), "backbone50.txt")
    if os.path.exists(backbone_path):
        with open(backbone_path) as f:
            for line in f:
                sym = line.strip().replace(".NS", "")
                if sym:
                    extra_symbols.add(sym)
    # Nifty200
    n200_path = os.path.join(os.path.dirname(output_dir), "nifty200.txt")
    if os.path.exists(n200_path):
        with open(n200_path) as f:
            for line in f:
                sym = line.strip().replace(".NS", "")
                if sym:
                    extra_symbols.add(sym)

    print(f"Ensuring {len(extra_symbols)} extra symbols are mapped...\n")
    sector_map, symbol_industries = build_sector_map(extra_symbols=list(extra_symbols))

    # Save sector map
    sector_path = os.path.join(output_dir, "nse_sectors.json")
    with open(sector_path, "w") as f:
        json.dump(sector_map, f, indent=2, sort_keys=True)
    print(f"\nSaved sector map: {sector_path}")

    # Save industry map (for reference/debugging)
    ind_path = os.path.join(output_dir, "nse_industries.json")
    with open(ind_path, "w") as f:
        json.dump(symbol_industries, f, indent=2, sort_keys=True)
    print(f"Saved industry map: {ind_path}")

    # Verify today's picks
    verify_picks(sector_map, symbol_industries)

    print(f"\n{'='*60}")
    print(f"  DONE — {len(sector_map)} stocks mapped to sectors")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
