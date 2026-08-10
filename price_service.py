"""
NSE Price Service — Bhavcopy (EOD) + yfinance (historical/realtime).

Data sources:
  1. NSE Bhavcopy (CM-BHAVDATA-FULL) — official EOD data, all ~2000 NSE stocks in one download
  2. yfinance — historical OHLC for pattern scanning, 15-min delayed quotes

Architecture:
  - get_eod(date)          → bhavcopy (cached forever)
  - get_ohlc(symbol, period) → yfinance one-time + bhavcopy daily updates
  - get_quote(symbol)       → yfinance (cached 1 min)
  - get_stock_universe()    → from latest bhavcopy
  - Cache: Redis (Docker) or disk (local)

CLI:
  python price_service.py --bhavcopy              # download today's bhavcopy
  python price_service.py --test RELIANCE          # test OHLC fetch
  python price_service.py --quote RELIANCE         # real-time quote
  python price_service.py --universe               # list all NSE stocks
  python price_service.py --batch 50               # batch test 50 stocks
"""

import os
import sys
import json
import time
import hashlib
import logging
import io
import zipfile
from datetime import datetime, timedelta, date
from typing import Optional

import pandas as pd

# curl_cffi for NSE (bypasses Akamai), yfinance for historical
try:
    from curl_cffi import requests as cffi_requests
    USE_CFFI = True
except ImportError:
    import requests
    cffi_requests = None
    USE_CFFI = False

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("price_service")

# ── Constants ────────────────────────────────────────────────────────
NSE_BASE = "https://www.nseindia.com"
NSE_DAILY_REPORTS = "https://www.nseindia.com/api/daily-reports"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
API_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_BASE,
    "X-Requested-With": "XMLHttpRequest",
}
CACHE_TTL_OHLC = 28800       # 8 hours
CACHE_TTL_QUOTE = 60         # 1 minute
CACHE_TTL_BHAVCOPY = 999999  # forever (historical data doesn't change)
CACHE_TTL_UNIVERSE = 86400   # 24 hours


class DiskCache:
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        h = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{h}.json")

    def get(self, key: str, ttl: int) -> Optional[any]:
        path = self._path(key)
        if not os.path.isfile(path):
            return None
        mtime = os.path.getmtime(path)
        if time.time() - mtime > ttl:
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def set(self, key: str, value: any, ttl: int = 0):
        path = self._path(key)
        try:
            with open(path, "w") as f:
                json.dump(value, f)
        except (IOError, TypeError) as e:
            log.warning(f"Cache write failed: {e}")


class RedisCache:
    def __init__(self, redis_url: str):
        import redis
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.r.ping()

    def get(self, key: str, ttl: int) -> Optional[any]:
        val = self.r.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: any, ttl: int = 0):
        if ttl:
            self.r.setex(key, ttl, json.dumps(value))
        else:
            self.r.set(key, json.dumps(value))


class PriceService:
    """NSE Bhavcopy + yfinance price service with dual cache."""

    def __init__(self, redis_url: str = "", cache_dir: str = "cache"):
        # Cache
        self.cache = None
        redis_url = redis_url or os.getenv("REDIS_URL", "")
        if redis_url:
            try:
                self.cache = RedisCache(redis_url)
                log.info("Using Redis cache")
            except Exception:
                self.cache = None
        if self.cache is None:
            self.cache = DiskCache(cache_dir)
            log.info(f"Using disk cache: {cache_dir}/")

        # NSE session (for bhavcopy)
        self._nse_session = None
        self._nse_session_init_time = 0

        # yfinance import (lazy)
        self._yf = None

    @property
    def yf(self):
        if self._yf is None:
            import yfinance
            self._yf = yfinance
        return self._yf

    # ── NSE Session (for bhavcopy download) ─────────────────────────

    def _get_nse_session(self):
        """Get or create a curl_cffi session with NSE cookies."""
        if self._nse_session and time.time() - self._nse_session_init_time < 3600:
            return self._nse_session

        if not USE_CFFI:
            import requests
            s = requests.Session()
            s.headers.update(BROWSER_HEADERS)
            try:
                s.get(NSE_BASE, timeout=15)
            except Exception:
                pass
            self._nse_session = s
            self._nse_session_init_time = time.time()
            return s

        s = cffi_requests.Session(impersonate="chrome")
        s.headers.update(BROWSER_HEADERS)
        try:
            s.get(NSE_BASE, timeout=15)
            time.sleep(1)
        except Exception as e:
            log.warning(f"NSE session init warning: {e}")
        self._nse_session = s
        self._nse_session_init_time = time.time()
        log.info("NSE session initialized")
        return s

    # ── Bhavcopy (EOD data for ALL stocks) ──────────────────────────

    def download_bhavcopy(self, target_date: date = None) -> Optional[pd.DataFrame]:
        """
        Download NSE bhavcopy for a given date (or today/previous trading day).

        Returns DataFrame with: symbol, open, high, low, close, volume, prev_close, etc.
        Cached forever (EOD data doesn't change).
        """
        if target_date is None:
            target_date = date.today()

        date_str = target_date.isoformat()
        cache_key = f"bhavcopy:{date_str}"
        cached = self.cache.get(cache_key, CACHE_TTL_BHAVCOPY)
        if cached:
            df = pd.DataFrame(cached["data"])
            log.info(f"Bhavcopy {date_str}: {len(df)} stocks (cached)")
            return df

        s = self._get_nse_session()

        # Try daily-reports API (works for current + previous trading day)
        try:
            resp = s.get(f"{NSE_DAILY_REPORTS}?key=CM", timeout=10,
                         headers={**API_HEADERS, "Accept": "application/json"})
            if resp.status_code == 200:
                reports = resp.json()
                # Find CM-BHAVDATA-FULL
                for day_type in ["CurrentDay", "PreviousDay"]:
                    for f in reports.get(day_type, []):
                        if f.get("fileKey") == "CM-BHAVDATA-FULL":
                            url = f"{f['filePath']}{f['fileActlName']}"
                            log.info(f"Downloading bhavcopy: {url}")
                            resp2 = s.get(url, timeout=30, headers={
                                "Accept": "text/csv,application/octet-stream,*/*",
                                "Referer": "https://www.nseindia.com/all-reports",
                            })
                            log.info(f"  Download response: {resp2.status_code}, {len(resp2.content)} bytes")
                            if resp2.status_code == 200 and len(resp2.content) > 1000:
                                df = self._parse_bhavdata_full(resp2.text)
                                log.info(f"  Parsed: {len(df) if df is not None else 'None'} rows")
                                if df is not None and not df.empty:
                                    self.cache.set(cache_key, {
                                        "data": df.to_dict(orient="records"),
                                        "date": date_str,
                                    })
                                    log.info(f"Bhavcopy {date_str}: {len(df)} stocks downloaded")
                                    return df
                            else:
                                log.warning(f"Bhavcopy download returned {resp2.status_code} ({len(resp2.content)} bytes)")
        except Exception as e:
            log.warning(f"Daily reports API failed: {e}")

        # Fallback: try historical archives URL
        try:
            dd = target_date.strftime("%d")
            MMM = target_date.strftime("%b").upper()
            yyyy = target_date.year
            url = f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{yyyy}/{MMM}/cm{dd}{MMM}{yyyy}bhav.csv.zip"
            log.info(f"Trying archives: {url}")
            resp = s.get(url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 1000:
                fp = io.BytesIO(resp.content)
                with zipfile.ZipFile(fp) as zf:
                    fname = zf.namelist()[0]
                    with zf.open(fname) as csvf:
                        content = csvf.read().decode("utf-8")
                        df = self._parse_bhavcopy_csv(content)
                        if df is not None and not df.empty:
                            self.cache.set(cache_key, {
                                "data": df.to_dict(orient="records"),
                                "date": date_str,
                            })
                            log.info(f"Bhavcopy {date_str}: {len(df)} stocks (archives)")
                            return df
        except Exception as e:
            log.warning(f"Archives download failed: {e}")

        log.error(f"Failed to download bhavcopy for {date_str}")
        return None

    def _parse_bhavdata_full(self, csv_text: str) -> Optional[pd.DataFrame]:
        """Parse CM-BHAVDATA-FULL CSV format."""
        try:
            df = pd.read_csv(io.StringIO(csv_text))
            df.columns = [c.strip() for c in df.columns]
            # Strip whitespace from all string columns
            for c in df.select_dtypes(include=["object"]).columns:
                df[c] = df[c].str.strip()
            # Filter EQ series only
            if "SERIES" in df.columns:
                df = df[df["SERIES"] == "EQ"].copy()
            # Rename to standard columns
            rename = {
                "SYMBOL": "symbol",
                "OPEN_PRICE": "open",
                "HIGH_PRICE": "high",
                "LOW_PRICE": "low",
                "CLOSE_PRICE": "close",
                "LAST_PRICE": "last",
                "PREV_CLOSE": "prev_close",
                "TTL_TRD_QNTY": "volume",
                "TURNOVER_LACS": "turnover_lacs",
                "NO_OF_TRADES": "trades",
                "DELIV_QTY": "deliv_qty",
                "DELIV_PER": "deliv_pct",
                "DATE1": "date",
            }
            df = df.rename(columns=rename)
            numeric_cols = ["open", "high", "low", "close", "last", "prev_close",
                    "volume", "trades", "deliv_qty", "deliv_pct"]
            for c in numeric_cols:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            keep = ["symbol"] + [c for c in numeric_cols if c in df.columns]
            return df[keep]
        except Exception as e:
            log.error(f"Parse bhavdata failed: {e}")
            return None

    def _parse_bhavcopy_csv(self, csv_text: str) -> Optional[pd.DataFrame]:
        """Parse standard NSE bhavcopy CSV (from archives zip)."""
        try:
            df = pd.read_csv(io.StringIO(csv_text))
            df.columns = [c.strip() for c in df.columns]
            for c in df.select_dtypes(include=["object"]).columns:
                df[c] = df[c].str.strip()
            if "SERIES" in df.columns:
                df = df[df["SERIES"] == "EQ"].copy()
            rename = {
                "SYMBOL": "symbol",
                "OPEN_PRICE": "open",
                "HIGH_PRICE": "high",
                "LOW_PRICE": "low",
                "CLOSE_PRICE": "close",
                "LAST_PRICE": "last",
                "PREV_CL_PR": "prev_close",
                "TOTTRDQTY": "volume",
                "TOTTRDVAL": "turnover",
                "TOTALTRADES": "trades",
                "DELIVQTY": "deliv_qty",
                "DELIVPER": "deliv_pct",
            }
            df = df.rename(columns=rename)
            numeric_cols = ["open", "high", "low", "close", "last", "prev_close",
                    "volume", "trades", "deliv_qty", "deliv_pct"]
            for c in numeric_cols:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            keep = ["symbol"] + [c for c in numeric_cols if c in df.columns]
            return df[keep]
        except Exception as e:
            log.error(f"Parse bhavcopy failed: {e}")
            return None

    # ── EOD data (from bhavcopy) ────────────────────────────────────

    def get_eod(self, symbol: str, target_date: date = None) -> Optional[dict]:
        """Get EOD data for a single stock from bhavcopy."""
        symbol = symbol.replace(".NS", "").replace(".BO", "")
        df = self.download_bhavcopy(target_date)
        if df is None:
            return None
        row = df[df["symbol"] == symbol]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def get_eod_all(self, target_date: date = None) -> Optional[pd.DataFrame]:
        """Get EOD data for ALL stocks (the full bhavcopy)."""
        return self.download_bhavcopy(target_date)

    # ── Stock Universe (from bhavcopy) ──────────────────────────────

    def get_stock_universe(self) -> Optional[list[str]]:
        """Get all NSE EQ stock symbols from latest bhavcopy."""
        cache_key = "universe:eq"
        cached = self.cache.get(cache_key, CACHE_TTL_UNIVERSE)
        if cached:
            return cached

        df = self.download_bhavcopy()
        if df is not None and not df.empty:
            symbols = df["symbol"].tolist()
            self.cache.set(cache_key, symbols)
            return symbols
        return None

    # ── Historical OHLC (yfinance) ──────────────────────────────────

    def get_ohlc(self, symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        """Fetch historical OHLC via yfinance. Cached 8 hours.
        Resolves stale symbols via SYMBOL_ALIASES from data.loader."""
        symbol_clean = symbol.replace(".NS", "").replace(".BO", "")

        # Resolve stale symbols (e.g. ZOMATO → ETERNAL, REC → RECLTD)
        try:
            from data.loader import SYMBOL_ALIASES, KNOWN_DELISTED
            if symbol_clean in KNOWN_DELISTED:
                return None
            symbol_clean = SYMBOL_ALIASES.get(symbol_clean, symbol_clean)
        except ImportError:
            pass

        cache_key = f"ohlc:{symbol_clean}:{period}:{interval}"
        cached = self.cache.get(cache_key, CACHE_TTL_OHLC)
        if cached:
            df = pd.DataFrame(cached["data"])
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
            return df

        try:
            yf_symbol = f"{symbol_clean}.NS"
            ticker = self.yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return None
            df.columns = [c.replace(" ", "") for c in df.columns]
            df = df[["Open", "High", "Low", "Close", "Volume"]]

            # Cache it
            cache_data = df.reset_index().assign(
                Date=df.reset_index()["Date"].dt.strftime("%Y-%m-%d")
            ).to_dict(orient="records")
            self.cache.set(cache_key, {"data": cache_data})
            return df
        except Exception as e:
            log.error(f"yfinance failed for {symbol}: {e}")
            return None

    def get_ohlc_batch(self, symbols: list[str], period: str = "1y", interval: str = "1d",
                       show_progress: bool = True) -> dict[str, pd.DataFrame]:
        """Batch fetch OHLC for multiple stocks."""
        results = {}
        total = len(symbols)
        for i, sym in enumerate(symbols):
            if show_progress and (i % 10 == 0 or i == total - 1):
                log.info(f"Fetching {i+1}/{total}: {sym}")
            df = self.get_ohlc(sym, period=period, interval=interval)
            if df is not None and not df.empty:
                results[sym] = df
        if show_progress:
            log.info(f"Batch complete: {len(results)}/{total} succeeded")
        return results

    # ── Real-time Quote (yfinance, 15-min delayed) ──────────────────

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Get real-time quote via yfinance (15-min delayed). Cached 1 min."""
        symbol_clean = symbol.replace(".NS", "").replace(".BO", "")
        cache_key = f"quote:{symbol_clean}"
        cached = self.cache.get(cache_key, CACHE_TTL_QUOTE)
        if cached:
            return cached

        try:
            ticker = self.yf.Ticker(f"{symbol_clean}.NS")
            info = ticker.fast_info
            hist = ticker.history(period="1d")
            if hist.empty:
                return None
            last = hist.iloc[-1]
            quote = {
                "symbol": symbol_clean,
                "last_price": float(last["Close"]),
                "open": float(last["Open"]),
                "high": float(last["High"]),
                "low": float(last["Low"]),
                "close": float(last["Close"]),
                "volume": int(last["Volume"]),
                "change": 0,
                "change_pct": 0,
            }
            self.cache.set(cache_key, quote)
            return quote
        except Exception as e:
            log.error(f"Quote failed for {symbol}: {e}")
            return None


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="NSE Price Service")
    parser.add_argument("--bhavcopy", action="store_true", help="Download today's bhavcopy")
    parser.add_argument("--test", metavar="SYMBOL", help="Test OHLC fetch")
    parser.add_argument("--quote", metavar="SYMBOL", help="Real-time quote")
    parser.add_argument("--universe", action="store_true", help="List all NSE stocks")
    parser.add_argument("--batch", type=int, metavar="N", help="Batch test N stocks")
    parser.add_argument("--period", default="1y")
    args = parser.parse_args()

    ps = PriceService()

    if args.bhavcopy:
        print("\nDownloading NSE Bhavcopy...")
        t0 = time.time()
        df = ps.download_bhavcopy()
        t1 = time.time()
        if df is not None:
            print(f"  Stocks: {len(df)}")
            print(f"  Time: {t1-t0:.2f}s")
            print(f"\n  Top 5 by volume:")
            if "volume" in df.columns:
                top = df.nlargest(5, "volume")[["symbol", "close", "volume"]]
                print(top.to_string(index=False))
            print(f"\n  First 5 stocks:")
            print(df[["symbol", "open", "high", "low", "close"]].head().to_string(index=False))
        else:
            print("  FAILED")

    elif args.test:
        print(f"\nFetching OHLC for {args.test}...")
        df = ps.get_ohlc(args.test, period=args.period)
        if df is not None:
            print(f"  Rows: {len(df)}, Range: {df.index[0]} to {df.index[-1]}")
            print(df.tail(3).to_string())
        else:
            print("  FAILED")

    elif args.quote:
        print(f"\nQuote for {args.quote}...")
        q = ps.get_quote(args.quote)
        if q:
            print(f"  Last: Rs.{q['last_price']}, Open: {q['open']}, High: {q['high']}, Low: {q['low']}")
        else:
            print("  FAILED")

    elif args.universe:
        print("\nFetching stock universe...")
        stocks = ps.get_stock_universe()
        if stocks:
            print(f"  Total: {len(stocks)} stocks")
            print(f"  First 20: {', '.join(stocks[:20])}")
        else:
            print("  FAILED")

    elif args.batch:
        from pathlib import Path
        nifty500_path = Path(__file__).parent.parent / "scanner-v3" / "nifty500.txt"
        if nifty500_path.exists():
            with open(nifty500_path) as f:
                symbols = [l.strip().replace(".NS", "") for l in f
                           if l.strip() and not l.strip().startswith("#")]
        else:
            symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
                       "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK"]
        symbols = symbols[:args.batch]
        t0 = time.time()
        results = ps.get_ohlc_batch(symbols, period=args.period)
        t1 = time.time()
        print(f"\n  Success: {len(results)}/{len(symbols)} in {t1-t0:.1f}s")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
