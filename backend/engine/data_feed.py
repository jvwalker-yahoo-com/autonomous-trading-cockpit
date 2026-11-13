"""
Data feed module with Finnhub REST API integration and high-fidelity fallback simulator.
Fetches real-time quotes, calculates technical indicators, maintains rolling tick history,
and estimates market micro-structure (spreads, depth, sentiment).
"""
import time
import math
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from .screener import MASTER_STOCK_UNIVERSE

# Reference seed prices for all 100+ US equities, high-beta assets & ETFs
BASE_PRICES: Dict[str, float] = {
    sym: data["base_price"] for sym, data in MASTER_STOCK_UNIVERSE.items()
}
# Fallback defaults for major indices/cryptos if requested
BASE_PRICES.update({
    "BTC": 64200.0, "ETH": 2540.0, "SOL": 142.0, "XRP": 0.58, "GOLD": 2510.0, "OIL": 74.50
})


class MarketDataPoint:
    def __init__(
        self,
        symbol: str,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        open_p: Optional[float] = None,
        prev_close: Optional[float] = None,
        volume: float = 100000.0,
        timestamp: Optional[float] = None,
        source: str = "simulated",
    ):
        self.symbol = symbol
        self.price = float(price)
        self.high = float(price if high is None else high)
        self.low = float(price if low is None else low)
        self.open = float(price if open_p is None else open_p)
        self.prev_close = float(price if prev_close is None else prev_close)
        self.volume = float(volume)
        self.timestamp = time.time() if timestamp is None else float(timestamp)
        self.source = source
        self.change = self.price - self.prev_close
        self.change_pct = (self.change / self.prev_close) * 100.0 if self.prev_close > 0 else 0.0

from .indicators import TechnicalIndicators

class DataFeedManager:
    def __init__(
        self,
        api_key: str = "",
        twelve_data_api_key: str = "",
        fmp_api_key: str = "",
        alpha_vantage_api_key: str = ""
    ):
        self.api_key = api_key.strip() # Finnhub API Key
        self.twelve_data_api_key = twelve_data_api_key.strip()
        self.fmp_api_key = fmp_api_key.strip()
        self.alpha_vantage_api_key = alpha_vantage_api_key.strip()

        self._lock = threading.RLock()
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=32)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self.history_windows: Dict[str, List[float]] = {}
        self.high_windows: Dict[str, List[float]] = {}
        self.low_windows: Dict[str, List[float]] = {}
        self.open_windows: Dict[str, List[float]] = {}
        self.volume_windows: Dict[str, List[float]] = {}
        self._bar_versions: Dict[str, int] = {}
        self._indicator_cache: Dict[str, Tuple[Tuple[Any, ...], Dict[str, Any]]] = {}
        self._ohlcv_hydrated: Dict[str, float] = {}

        self.last_quotes: Dict[str, MarketDataPoint] = {}
        self.simulated_states: Dict[str, Dict[str, float]] = {}
        self._quote_cache: Dict[str, Tuple[float, MarketDataPoint]] = {}
        self._sentiment_cache: Dict[str, Tuple[float, float]] = {}
        self._finnhub_sentiment_disabled = False
        self._last_finnhub_call = 0.0
        self._last_twelve_call = 0.0
        self._last_fmp_call = 0.0
        self._last_av_call = 0.0
        self.last_api_call_time = 0.0
        self.api_latency_ms = 12.0
        self.active_feed_source = "finnhub"
        
        # Initialize historical buffers with synthetic warmup until hydrated from OHLCV API
        for symbol, base_p in BASE_PRICES.items():
            self._warmup_history(symbol, base_p)

    def _warmup_history(self, symbol: str, base_price: float):
        """Generates initial 60 periods of OHLCV warmup history until real bars hydrate."""
        prices: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        opens: List[float] = []
        volumes: List[float] = []
        p = max(0.00000001, base_price * (1.0 - random.uniform(0.01, 0.03)))
        precision = 8 if base_price < 0.01 else (4 if base_price < 1.0 else 2)
        for _ in range(60):
            open_p = round(p, precision)
            p = max(0.00000001, p + p * random.gauss(0.0001, 0.003))
            close_p = round(p, precision)
            wick = max(10 ** (-precision), close_p * random.uniform(0.001, 0.004))
            hi = round(max(open_p, close_p) + wick, precision)
            lo = round(max(10 ** (-precision), min(open_p, close_p) - wick), precision)
            opens.append(open_p)
            prices.append(close_p)
            highs.append(hi)
            lows.append(lo)
            volumes.append(round(random.uniform(50000, 250000), 0))
        with self._lock:
            self.open_windows[symbol] = opens
            self.history_windows[symbol] = prices
            self.high_windows[symbol] = highs
            self.low_windows[symbol] = lows
            self.volume_windows[symbol] = volumes
            self._bar_versions[symbol] = self._bar_versions.get(symbol, 0) + 1
            self.simulated_states[symbol] = {
                "price": prices[-1],
                "drift": random.uniform(-0.0002, 0.0002),
                "volatility": random.uniform(0.0015, 0.0040)
            }
            self.last_quotes[symbol] = MarketDataPoint(
                symbol=symbol,
                price=prices[-1],
                high=max(highs[-10:]),
                low=min(lows[-10:]),
                open_p=opens[0],
                prev_close=prices[0],
                volume=volumes[-1],
                timestamp=time.time(),
                source="warmup"
            )

    def ingest_ohlcv_bars(self, symbol: str, bars: List[Dict[str, Any]], source: str = "ohlcv") -> bool:
        """
        Replaces rolling symbol OHLCV buffers with chronological real candle history
        and bumps the indicator memoization version.
        """
        sym = symbol.upper().strip()
        opens: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        closes: List[float] = []
        vols: List[float] = []
        for b in bars[-120:]:
            c = float(b.get("close", b.get("c", 0.0)) or 0.0)
            if c <= 0:
                continue
            o = float(b.get("open", b.get("o", c)) or c)
            h = float(b.get("high", b.get("h", max(o, c))) or max(o, c))
            l = float(b.get("low", b.get("l", min(o, c))) or min(o, c))
            v = float(b.get("volume", b.get("v", 100000.0)) or 100000.0)
            opens.append(o)
            highs.append(max(h, o, c))
            lows.append(min(l, o, c))
            closes.append(c)
            vols.append(max(1.0, v))
        if not closes:
            return False
        with self._lock:
            self.open_windows[sym] = opens
            self.high_windows[sym] = highs
            self.low_windows[sym] = lows
            self.history_windows[sym] = closes
            self.volume_windows[sym] = vols
            self._bar_versions[sym] = self._bar_versions.get(sym, 0) + 1
            self._indicator_cache.pop(sym, None)
            self._ohlcv_hydrated[sym] = time.time()
            prev_c = closes[-2] if len(closes) >= 2 else closes[-1]
            existing = self.last_quotes.get(sym)
            if existing is None or existing.source in ("warmup", "simulated", "ohlcv"):
                self.last_quotes[sym] = MarketDataPoint(
                    symbol=sym,
                    price=closes[-1],
                    high=highs[-1],
                    low=lows[-1],
                    open_p=opens[-1],
                    prev_close=prev_c,
                    volume=vols[-1],
                    timestamp=time.time(),
                    source=source,
                )
        return True

    def record_bar_point(self, symbol: str, quote: MarketDataPoint):
        """Appends a new bar/tick into rolling OHLCV buffers and invalidates cached indicators."""
        sym = symbol.upper().strip()
        with self._lock:
            if sym not in self.history_windows:
                self._warmup_history(sym, quote.price)
            for attr, val in (
                (self.history_windows, float(quote.price)),
                (self.high_windows, float(max(quote.high, quote.price))),
                (self.low_windows, float(min(quote.low, quote.price))),
                (self.open_windows, float(quote.open)),
                (self.volume_windows, float(max(1.0, quote.volume))),
            ):
                buf = attr.setdefault(sym, [])
                buf.append(val)
                if len(buf) > 120:
                    buf.pop(0)
            self._bar_versions[sym] = self._bar_versions.get(sym, 0) + 1
            self._indicator_cache.pop(sym, None)
            self.last_quotes[sym] = quote

    def _fetch_symbol_ohlcv(self, symbol: str, count: int = 60) -> Tuple[List[Dict[str, float]], str]:
        """Fetches chronological daily OHLCV bars from Twelve Data, FMP, or Finnhub."""
        sym = symbol.upper().strip()
        if self.twelve_data_api_key and len(self.twelve_data_api_key) > 5:
            try:
                url = (
                    f"https://api.twelvedata.com/time_series?symbol={sym}&interval=1day"
                    f"&outputsize={count}&apikey={self.twelve_data_api_key}"
                )
                resp = self._session.get(url, timeout=3.0)
                if resp.status_code == 200:
                    vals = resp.json().get("values") or []
                    if isinstance(vals, list) and len(vals) >= 15:
                        bars = [
                            {
                                "open": float(v.get("open") or 0),
                                "high": float(v.get("high") or 0),
                                "low": float(v.get("low") or 0),
                                "close": float(v.get("close") or 0),
                                "volume": float(v.get("volume") or 100000.0),
                            }
                            for v in reversed(vals)
                        ]
                        return bars, "twelve_data"
            except Exception:
                pass

        if self.fmp_api_key and len(self.fmp_api_key) > 5:
            try:
                url = f"https://financialmodelingprep.com/stable/historical-price-eod/full?symbol={sym}&apikey={self.fmp_api_key}"
                resp = self._session.get(url, timeout=3.0)
                if resp.status_code == 200:
                    rows = resp.json()
                    if isinstance(rows, dict):
                        rows = rows.get("historical", [])
                    if isinstance(rows, list) and len(rows) >= 15:
                        bars = [
                            {
                                "open": float(r.get("open") or 0),
                                "high": float(r.get("high") or 0),
                                "low": float(r.get("low") or 0),
                                "close": float(r.get("close") or 0),
                                "volume": float(r.get("volume") or 100000.0),
                            }
                            for r in reversed(rows[:count])
                        ]
                        return bars, "fmp"
            except Exception:
                pass

        if self.api_key and len(self.api_key) > 5:
            try:
                now_ts = int(time.time())
                from_ts = now_ts - (count * 2 * 86400)
                url = f"https://finnhub.io/api/v1/stock/candle?symbol={sym}&resolution=D&from={from_ts}&to={now_ts}&token={self.api_key}"
                resp = self._session.get(url, timeout=3.0)
                if resp.status_code == 200:
                    d = resp.json()
                    if d.get("s") == "ok" and isinstance(d.get("c"), list) and len(d["c"]) >= 15:
                        c_arr, h_arr, l_arr, o_arr, v_arr = d["c"], d["h"], d["l"], d["o"], d["v"]
                        bars = [
                            {
                                "open": float(o_arr[i]),
                                "high": float(h_arr[i]),
                                "low": float(l_arr[i]),
                                "close": float(c_arr[i]),
                                "volume": float(v_arr[i] or 100000.0),
                            }
                            for i in range(len(c_arr))
                        ]
                        return bars, "finnhub"
            except Exception:
                pass

        return [], ""

    def hydrate_historical_ohlcv(self, symbols: List[str], count: int = 60, max_workers: int = 4) -> int:
        """Concurrently hydrates real OHLCV candle history for symbols missing recent real bars."""
        now = time.time()
        targets = [
            s.upper().strip()
            for s in dict.fromkeys(symbols)
            if (now - self._ohlcv_hydrated.get(s.upper().strip(), 0.0)) >= 3600.0
        ]
        if not targets:
            return 0
        # Only attempt network hydration if at least one candle provider key is configured
        if not (len(self.twelve_data_api_key) > 5 or len(self.fmp_api_key) > 5 or len(self.api_key) > 5):
            return 0

        hydrated = 0
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(targets)))) as pool:
            futs = {pool.submit(self._fetch_symbol_ohlcv, sym, count): sym for sym in targets[:25]}
            for fut in as_completed(futs):
                sym = futs[fut]
                try:
                    bars, src = fut.result()
                    if bars and self.ingest_ohlcv_bars(sym, bars, source=src or "ohlcv"):
                        hydrated += 1
                except Exception:
                    pass
        return hydrated

    def set_api_key(self, key: str):
        self.api_key = key.strip()

    def set_feed_keys(self, finnhub_key: str = "", twelve_data_key: str = "", fmp_key: str = "", alpha_vantage_key: str = ""):
        if finnhub_key:
            self.api_key = finnhub_key.strip()
        if twelve_data_key:
            self.twelve_data_api_key = twelve_data_key.strip()
        if fmp_key:
            self.fmp_api_key = fmp_key.strip()
        if alpha_vantage_key:
            self.alpha_vantage_api_key = alpha_vantage_key.strip()

    def get_latest_quote(self, symbol: str, max_cache_age_sec: float = 15.0, allow_external: bool = True) -> MarketDataPoint:
        """
        Fetches live quote with 15s TTL caching, pooled HTTP connections, and multi-provider failover:
        1. Finnhub
        2. Twelve Data
        3. Financial Modeling Prep (FMP)
        4. Alpha Vantage
        5. Recent real quote grace cache (< 120s) before simulated fallback
        """
        sym = symbol.upper().strip()
        now = time.time()
        start_t = time.perf_counter()

        # 1. Fast Cache Hit (within TTL)
        with self._lock:
            cached = self._quote_cache.get(sym)
            if cached:
                cached_t, cached_quote = cached
                if (now - cached_t) < max_cache_age_sec:
                    return cached_quote

        quote = None

        # 2. External multi-provider cascade (only if allow_external is True)
        if allow_external:
            # Priority 1: Finnhub API (Thread-safe rate window)
            run_fh = False
            if self.api_key and len(self.api_key) > 5:
                with self._lock:
                    if (now - self._last_finnhub_call) >= 0.45:
                        self._last_finnhub_call = now
                        run_fh = True
            if run_fh:
                try:
                    url = f"https://finnhub.io/api/v1/quote?symbol={sym}&token={self.api_key}"
                    resp = self._session.get(url, timeout=1.5)
                    if resp.status_code == 200:
                        data = resp.json()
                        c = data.get("c", 0.0)
                        if c and float(c) > 0:
                            self.api_latency_ms = max(1.0, (time.perf_counter() - start_t) * 1000.0)
                            self.last_api_call_time = now
                            self.active_feed_source = "finnhub"
                            prev_vol = self.volume_windows.get(sym, [150000.0])[-1]
                            quote = MarketDataPoint(
                                symbol=sym,
                                price=float(c),
                                high=float(data.get("h") or c),
                                low=float(data.get("l") or c),
                                open_p=float(data.get("o") or c),
                                prev_close=float(data.get("pc") or c),
                                volume=prev_vol,
                                timestamp=float(data.get("t") or time.time()),
                                source="finnhub"
                            )
                except Exception:
                    pass

            # Priority 2: Twelve Data API (if Finnhub missed or rate-limited)
            run_td = False
            if quote is None and self.twelve_data_api_key and len(self.twelve_data_api_key) > 5:
                with self._lock:
                    if (now - self._last_twelve_call) >= 0.45:
                        self._last_twelve_call = now
                        run_td = True
            if run_td:
                try:
                    url = f"https://api.twelvedata.com/quote?symbol={sym}&apikey={self.twelve_data_api_key}"
                    resp = self._session.get(url, timeout=1.8)
                    if resp.status_code == 200:
                        data = resp.json()
                        c_str = data.get("close") or data.get("price")
                        if c_str:
                            c = float(c_str)
                            if c > 0:
                                h = float(data.get("high") or c)
                                l = float(data.get("low") or c)
                                o = float(data.get("open") or c)
                                pc = float(data.get("previous_close") or c)
                                prev_vol = self.volume_windows.get(sym, [150000.0])[-1]
                                vol = float(data.get("volume") or prev_vol)
                                self.api_latency_ms = max(1.0, (time.perf_counter() - start_t) * 1000.0)
                                self.last_api_call_time = now
                                self.active_feed_source = "twelve_data"
                                quote = MarketDataPoint(
                                    symbol=sym,
                                    price=c,
                                    high=h,
                                    low=l,
                                    open_p=o,
                                    prev_close=pc,
                                    volume=vol,
                                    timestamp=time.time(),
                                    source="twelve_data"
                                )
                except Exception:
                    pass

            # Priority 3: Financial Modeling Prep (FMP Stable API)
            run_fmp = False
            if quote is None and self.fmp_api_key and len(self.fmp_api_key) > 5:
                with self._lock:
                    if (now - self._last_fmp_call) >= 0.45:
                        self._last_fmp_call = now
                        run_fmp = True
            if run_fmp:
                try:
                    url = f"https://financialmodelingprep.com/stable/quote?symbol={sym}&apikey={self.fmp_api_key}"
                    resp = self._session.get(url, timeout=1.8)
                    if resp.status_code == 200:
                        data_list = resp.json()
                        if isinstance(data_list, list) and len(data_list) > 0:
                            row = data_list[0]
                            c = float(row.get("price") or 0.0)
                            if c > 0:
                                h = float(row.get("dayHigh") or c)
                                l = float(row.get("dayLow") or c)
                                o = float(row.get("open") or c)
                                pc = float(row.get("previousClose") or c)
                                prev_vol = self.volume_windows.get(sym, [150000.0])[-1]
                                vol = float(row.get("volume") or prev_vol)
                                self.api_latency_ms = max(1.0, (time.perf_counter() - start_t) * 1000.0)
                                self.last_api_call_time = now
                                self.active_feed_source = "fmp"
                                quote = MarketDataPoint(
                                    symbol=sym,
                                    price=c,
                                    high=h,
                                    low=l,
                                    open_p=o,
                                    prev_close=pc,
                                    volume=vol,
                                    timestamp=time.time(),
                                    source="fmp"
                                )
                except Exception:
                    pass

            # Priority 4: Alpha Vantage GLOBAL_QUOTE
            run_av = False
            if quote is None and self.alpha_vantage_api_key and len(self.alpha_vantage_api_key) > 5:
                with self._lock:
                    if (now - self._last_av_call) >= 0.9:
                        self._last_av_call = now
                        run_av = True
            if run_av:
                try:
                    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={sym}&apikey={self.alpha_vantage_api_key}"
                    resp = self._session.get(url, timeout=2.0)
                    if resp.status_code == 200:
                        gq = resp.json().get("Global Quote", {})
                        p_str = gq.get("05. price")
                        if p_str:
                            c = float(p_str)
                            if c > 0:
                                h = float(gq.get("03. high") or c)
                                l = float(gq.get("04. low") or c)
                                o = float(gq.get("02. open") or c)
                                pc = float(gq.get("08. previous close") or c)
                                prev_vol = self.volume_windows.get(sym, [150000.0])[-1]
                                vol = float(gq.get("06. volume") or prev_vol)
                                self.api_latency_ms = max(1.0, (time.perf_counter() - start_t) * 1000.0)
                                self.last_api_call_time = now
                                self.active_feed_source = "alpha_vantage"
                                quote = MarketDataPoint(
                                    symbol=sym,
                                    price=c,
                                    high=h,
                                    low=l,
                                    open_p=o,
                                    prev_close=pc,
                                    volume=vol,
                                    timestamp=time.time(),
                                    source="alpha_vantage"
                                )
                except Exception:
                    pass

        # 6. Graceful fallback: preserve recent real quote (< 120s) before simulated tick
        if quote is None:
            if cached and (cached[1].source not in ("simulated", "warmup") or not allow_external) and (now - cached[0]) < 120.0:
                return cached[1]
            self.api_latency_ms = max(1.0, (time.perf_counter() - start_t) * 1000.0)
            self.active_feed_source = "simulated"
            quote = self._generate_simulated_tick(sym)

        # Cache valid quote and append bar point
        with self._lock:
            self._quote_cache[sym] = (now, quote)
        self.record_bar_point(sym, quote)
        return quote

    def fetch_quotes_batch(self, symbols: List[str], max_cache_age_sec: float = 15.0) -> Dict[str, MarketDataPoint]:
        """
        Pre-fetches quotes concurrently using multi-symbol batch endpoints (FMP / TwelveData)
        and bounded parallel Finnhub requests so the analysis loop avoids sequential blocking.
        """
        results: Dict[str, MarketDataPoint] = {}
        now = time.time()
        unique_syms = [s.upper().strip() for s in dict.fromkeys(symbols) if s and s.strip()]
        uncached: List[str] = []
        with self._lock:
            for sym in unique_syms:
                cached = self._quote_cache.get(sym)
                if cached and (now - cached[0]) < max_cache_age_sec:
                    results[sym] = cached[1]
                else:
                    uncached.append(sym)

        if not uncached:
            return results

        # Native batch fetch via FMP (up to 20 per call)
        if self.fmp_api_key and len(self.fmp_api_key) > 5 and uncached:
            still_needed: List[str] = []
            for i in range(0, len(uncached), 20):
                chunk = uncached[i:i + 20]
                try:
                    joined = ",".join(chunk)
                    url = f"https://financialmodelingprep.com/stable/quote?symbol={joined}&apikey={self.fmp_api_key}"
                    resp = self._session.get(url, timeout=2.5)
                    if resp.status_code == 200 and isinstance(resp.json(), list):
                        for row in resp.json():
                            s = str(row.get("symbol") or "").upper().strip()
                            c = float(row.get("price") or 0.0)
                            if s and c > 0:
                                q = MarketDataPoint(
                                    symbol=s,
                                    price=c,
                                    high=float(row.get("dayHigh") or c),
                                    low=float(row.get("dayLow") or c),
                                    open_p=float(row.get("open") or c),
                                    prev_close=float(row.get("previousClose") or c),
                                    volume=float(row.get("volume") or 150000.0),
                                    timestamp=now,
                                    source="fmp"
                                )
                                results[s] = q
                                with self._lock:
                                    self._quote_cache[s] = (now, q)
                                self.record_bar_point(s, q)
                except Exception:
                    pass
                for s in chunk:
                    if s not in results:
                        still_needed.append(s)
            uncached = still_needed

        # Native batch fetch via Twelve Data (up to 8 per call)
        if self.twelve_data_api_key and len(self.twelve_data_api_key) > 5 and uncached:
            still_needed = []
            for i in range(0, len(uncached), 8):
                chunk = uncached[i:i + 8]
                try:
                    joined = ",".join(chunk)
                    url = f"https://api.twelvedata.com/quote?symbol={joined}&apikey={self.twelve_data_api_key}"
                    resp = self._session.get(url, timeout=2.5)
                    if resp.status_code == 200:
                        payload = resp.json()
                        items = {chunk[0]: payload} if (len(chunk) == 1 and "close" in payload) else payload
                        if isinstance(items, dict):
                            for s_key, row in items.items():
                                if not isinstance(row, dict):
                                    continue
                                c_str = row.get("close") or row.get("price")
                                if c_str:
                                    c = float(c_str)
                                    if c > 0:
                                        s = s_key.upper().strip()
                                        q = MarketDataPoint(
                                            symbol=s,
                                            price=c,
                                            high=float(row.get("high") or c),
                                            low=float(row.get("low") or c),
                                            open_p=float(row.get("open") or c),
                                            prev_close=float(row.get("previous_close") or c),
                                            volume=float(row.get("volume") or 150000.0),
                                            timestamp=now,
                                            source="twelve_data"
                                        )
                                        results[s] = q
                                        with self._lock:
                                            self._quote_cache[s] = (now, q)
                                        self.record_bar_point(s, q)
                except Exception:
                    pass
                for s in chunk:
                    if s not in results:
                        still_needed.append(s)
            uncached = still_needed

        # Bounded parallel fallback for any remaining symbols (e.g. Finnhub / simulated)
        if uncached:
            with ThreadPoolExecutor(max_workers=min(4, len(uncached))) as pool:
                futs = {pool.submit(self.get_latest_quote, sym, max_cache_age_sec, True): sym for sym in uncached[:20]}
                for fut in as_completed(futs):
                    sym = futs[fut]
                    try:
                        results[sym] = fut.result()
                    except Exception:
                        pass
        return results


    def _generate_simulated_tick(self, symbol: str) -> MarketDataPoint:
        state = self.simulated_states.get(symbol)
        if not state:
            base_p = BASE_PRICES.get(symbol, 150.0)
            self._warmup_history(symbol, base_p)
            state = self.simulated_states[symbol]
        
        # Periodic random regime shifts
        if random.random() < 0.05:
            state["drift"] = random.uniform(-0.001, 0.001)
        
        current_p = state["price"]
        step = current_p * (state["drift"] + random.gauss(0, state["volatility"]))
        precision = 8 if current_p < 0.01 else (4 if current_p < 1.0 else 2)
        min_p = 10 ** (-precision)
        new_p = max(min_p, round(current_p + step, precision))
        state["price"] = new_p
        
        hist = self.history_windows.get(symbol, [new_p])
        high_p = max(max(hist[-15:]), new_p)
        low_p = min(min(hist[-15:]), new_p)
        open_p = hist[0] if hist else new_p
        prev_close = BASE_PRICES.get(symbol, new_p)

        return MarketDataPoint(
            symbol=symbol,
            price=new_p,
            high=high_p,
            low=low_p,
            open_p=open_p,
            prev_close=prev_close,
            volume=random.uniform(50000, 300000),
            timestamp=time.time()
        )

    def get_technical_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        Calculates comprehensive quantitative indicators based on cinar/indicator:
        EMA(9), EMA(21), RSI(14), MACD, Bollinger Bands, ATR, ADX, SuperTrend, VWAP, MFI, and Keltner Channels.
        Uses real OHLCV candle buffers when available and memoizes by (bar_version, bar_shape).
        """
        sym = symbol.upper().strip()
        with self._lock:
            prices = np.array(self.history_windows.get(sym, [100.0]), dtype=float)
            volumes = np.array(self.volume_windows.get(sym, [100000.0]), dtype=float)
            h_win = self.high_windows.get(sym)
            l_win = self.low_windows.get(sym)
            o_win = self.open_windows.get(sym)
            bar_ver = self._bar_versions.get(sym, 0)

        highs = np.array(h_win, dtype=float) if (h_win is not None and len(h_win) == len(prices)) else (prices * 1.004)
        lows = np.array(l_win, dtype=float) if (l_win is not None and len(l_win) == len(prices)) else (prices * 0.996)
        opens = np.array(o_win, dtype=float) if (o_win is not None and len(o_win) == len(prices)) else (
            np.concatenate(([prices[0]], prices[:-1])) if len(prices) > 0 else np.array([100.0])
        )

        cache_sig = (
            bar_ver,
            len(prices),
            float(prices[-1]) if len(prices) > 0 else 0.0,
            float(highs[-1]) if len(highs) > 0 else 0.0,
            float(lows[-1]) if len(lows) > 0 else 0.0,
            float(volumes[-1]) if len(volumes) > 0 else 0.0,
        )
        with self._lock:
            cached = self._indicator_cache.get(sym)
            if cached and cached[0] == cache_sig:
                return cached[1]

        if len(prices) < 20:
            p = float(prices[-1])
            short_res = {
                "ema_9": p,
                "ema_21": p,
                "rsi_14": 50.0,
                "macd_line": 0.0,
                "macd_signal": 0.0,
                "bb_upper": round(p * 1.02, 2),
                "bb_lower": round(p * 0.98, 2),
                "bb_mid": p,
                "atr": round(p * 0.015, 2),
                "volatility_std": round(p * 0.01, 2),
                "adx": 22.0,
                "plus_di": 20.0,
                "minus_di": 20.0,
                "supertrend_val": round(p * 0.98, 2),
                "supertrend_dir": 1.0,
                "vwap": p,
                "mfi": 50.0,
                "keltner_upper": round(p * 1.02, 2),
                "keltner_mid": p,
                "keltner_lower": round(p * 0.98, 2),
                "volume_surge": 1.0,
                "breakout_type": "NONE",
                "breakout_level": 0.0,
                "double_bottom_detected": 0.0,
                "double_bottom_neckline": 0.0,
                "double_bottom_conf": 0.0,
                "double_top_detected": 0.0,
                "double_top_neckline": 0.0,
                "double_top_conf": 0.0,
                "chip_support": round(p * 0.98, 2),
                "chip_resistance": round(p * 1.02, 2),
                "dual_thrust_signal": "NONE",
                "dual_thrust_buy_line": round(p * 1.01, 2),
                "dual_thrust_sell_line": round(p * 0.99, 2),
                "london_breakout_signal": "NONE",
                "london_range_high": round(p * 1.005, 2),
                "london_range_low": round(p * 0.995, 2),
                "heikin_ashi_trend": "CHOPPY",
                "heikin_ashi_consecutive": 0,
                "wyckoff_structure": "NEUTRAL",
                "wyckoff_phase": "Phase A: Stopping The Prior Trend",
                "wyckoff_phase_code": "A",
                "wyckoff_bias": "EQUILIBRIUM",
                "wyckoff_signal": "HOLD",
                "wyckoff_creek": round(p * 1.02, 2),
                "wyckoff_ice": round(p * 0.98, 2),
                "wyckoff_climax_score": 0,
                "wyckoff_spring_score": 0,
                "wyckoff_utad_score": 0,
                "wyckoff_tp1": round(p * 1.01, 2),
                "wyckoff_tp2": round(p * 1.02, 2),
                "wyckoff_tp3": round(p * 1.03, 2),
                "wyckoff_sl": round(p * 0.98, 2),
                "wyckoff_data": {}
            }
            with self._lock:
                self._indicator_cache[sym] = (cache_sig, short_res)
            return short_res

        # 1. EMAs & MACD
        ema_9 = TechnicalIndicators.calc_ema(prices, 9)
        ema_21 = TechnicalIndicators.calc_ema(prices, 21)
        ema_12 = TechnicalIndicators.calc_ema(prices, 12)
        ema_26 = TechnicalIndicators.calc_ema(prices, 26)
        macd_line = ema_12 - ema_26
        macd_signal = TechnicalIndicators.calc_ema(prices[-9:], 9) - TechnicalIndicators.calc_ema(prices[-26:], 26)

        # 2. RSI(14)
        deltas = np.diff(prices[-15:])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains) if len(gains) > 0 else 0.001
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        # 3. Bollinger Bands
        window = prices[-20:]
        bb_mid = float(np.mean(window))
        std = float(np.std(window))
        bb_upper = bb_mid + (2.0 * std)
        bb_lower = bb_mid - (2.0 * std)

        # 4. ATR
        atr = TechnicalIndicators.calc_atr(highs, lows, prices, 14)

        # 5. cinar/indicator: ADX Trend Strength
        adx, plus_di, minus_di = TechnicalIndicators.calc_adx(highs, lows, prices, 14)

        # 6. cinar/indicator: SuperTrend
        st_val, st_dir = TechnicalIndicators.calc_supertrend(highs, lows, prices, 10, 3.0)

        # 7. cinar/indicator: VWAP
        vwap = TechnicalIndicators.calc_vwap(prices, volumes)

        # 8. cinar/indicator: MFI
        mfi = TechnicalIndicators.calc_mfi(highs, lows, prices, volumes, 14)

        # 9. cinar/indicator: Keltner Channels
        k_upper, k_mid, k_lower = TechnicalIndicators.calc_keltner_channel(highs, lows, prices, 20, 10, 2.0)

        # 10. myhhub/stock: Volume Surge Factor
        vol_surge = TechnicalIndicators.calc_volume_surge(volumes, 20)

        # 11. myhhub/stock: Range Breakout Detection
        breakout_type, breakout_level = TechnicalIndicators.detect_range_breakout(prices, highs, lows, 20)

        # 12. myhhub/stock: Candlestick Pattern Recognition (Double Bottom & Double Top)
        db_det, db_neck, db_conf = TechnicalIndicators.detect_double_bottom(prices)
        dt_det, dt_neck, dt_conf = TechnicalIndicators.detect_double_top(prices)

        # 13. myhhub/stock: Volume Chip Distribution (Cost Density)
        chips = TechnicalIndicators.calc_chip_distribution_density(prices, volumes)

        # 14. je-suis-tm/quant-trading: Dual Thrust Breakout
        dt_res = TechnicalIndicators.calc_dual_thrust(
            highs=highs,
            lows=lows,
            closes=prices,
            open_price=float(prices[0]),
            current_price=float(prices[-1])
        )

        # 15. je-suis-tm/quant-trading: London Open Breakout
        premarket_slice = prices[:min(10, len(prices))]
        london_res = TechnicalIndicators.calc_london_breakout(
            premarket_prices=premarket_slice,
            current_price=float(prices[-1])
        )

        # 16. je-suis-tm/quant-trading: Heikin-Ashi Candlestick Smoothing
        ha_res = TechnicalIndicators.calc_heikin_ashi(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=prices
        )

        # 17. Classic Wyckoff Range Engine (Accumulation/Distribution, Springs, UTADs, Multi-TP)
        wyckoff_res = TechnicalIndicators.calc_wyckoff(
            prices=prices,
            volumes=volumes,
            highs=highs,
            lows=lows,
            symbol=sym
        )

        result = {
            "ema_9": round(ema_9, 2),
            "ema_21": round(ema_21, 2),
            "rsi_14": round(float(rsi), 2),
            "macd_line": round(macd_line, 3),
            "macd_signal": round(macd_signal, 3),
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_mid": round(bb_mid, 2),
            "atr": round(atr, 3),
            "volatility_std": round(std, 3),
            "adx": round(adx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "supertrend_val": round(st_val, 2),
            "supertrend_dir": float(st_dir),
            "vwap": round(vwap, 2),
            "mfi": round(mfi, 2),
            "keltner_upper": round(k_upper, 2),
            "keltner_mid": round(k_mid, 2),
            "keltner_lower": round(k_lower, 2),
            "volume_surge": round(vol_surge, 2),
            "breakout_type": breakout_type,
            "breakout_level": round(breakout_level, 2),
            "double_bottom_detected": 1.0 if db_det else 0.0,
            "double_bottom_neckline": round(db_neck, 2),
            "double_bottom_conf": round(db_conf, 2),
            "double_top_detected": 1.0 if dt_det else 0.0,
            "double_top_neckline": round(dt_neck, 2),
            "double_top_conf": round(dt_conf, 2),
            "chip_support": round(chips.get("chip_support", 0.0), 2),
            "chip_resistance": round(chips.get("chip_resistance", 0.0), 2),
            "dual_thrust_signal": dt_res.get("dual_thrust_signal", "NONE"),
            "dual_thrust_buy_line": round(dt_res.get("dual_thrust_buy_line", 0.0), 2),
            "dual_thrust_sell_line": round(dt_res.get("dual_thrust_sell_line", 0.0), 2),
            "london_breakout_signal": london_res.get("london_breakout_signal", "NONE"),
            "london_range_high": round(london_res.get("london_range_high", 0.0), 2),
            "london_range_low": round(london_res.get("london_range_low", 0.0), 2),
            "heikin_ashi_trend": ha_res.get("ha_trend", "CHOPPY"),
            "heikin_ashi_consecutive": int(ha_res.get("ha_consecutive_bars", 0)),
            "wyckoff_structure": wyckoff_res.get("structure_type", "NEUTRAL"),
            "wyckoff_phase": wyckoff_res.get("phase", "Phase A: Stopping The Prior Trend"),
            "wyckoff_phase_code": wyckoff_res.get("phase_code", "A"),
            "wyckoff_bias": wyckoff_res.get("bias", "EQUILIBRIUM"),
            "wyckoff_signal": wyckoff_res.get("signal", "HOLD"),
            "wyckoff_creek": wyckoff_res.get("creek_resistance", round(prices[-1] * 1.02, 2)),
            "wyckoff_ice": wyckoff_res.get("ice_support", round(prices[-1] * 0.98, 2)),
            "wyckoff_climax_score": wyckoff_res.get("climax_score", 0),
            "wyckoff_spring_score": wyckoff_res.get("spring_quality_score", 0),
            "wyckoff_utad_score": wyckoff_res.get("utad_quality_score", 0),
            "wyckoff_tp1": wyckoff_res.get("trade_setup", {}).get("tp1", round(prices[-1] * 1.01, 2)),
            "wyckoff_tp2": wyckoff_res.get("trade_setup", {}).get("tp2", round(prices[-1] * 1.02, 2)),
            "wyckoff_tp3": wyckoff_res.get("trade_setup", {}).get("tp3", round(prices[-1] * 1.03, 2)),
            "wyckoff_sl": wyckoff_res.get("trade_setup", {}).get("stop_loss", round(prices[-1] * 0.98, 2)),
            "wyckoff_data": wyckoff_res
        }
        with self._lock:
            self._indicator_cache[sym] = (cache_sig, result)
        return result

    def get_news_sentiment(self, symbol: str) -> float:
        """
        Returns a sentiment score between -1.0 (very bearish) and +1.0 (very bullish).
        Utilizes 10-minute caching to eliminate blocking external HTTP calls.
        """
        now = time.time()
        cached = self._sentiment_cache.get(symbol)
        if cached:
            cached_t, score = cached
            if (now - cached_t) < 600.0:
                return score

        # 1. External Finnhub News Sentiment (if supported and enabled)
        if self.api_key and len(self.api_key) > 5 and not self._finnhub_sentiment_disabled:
            try:
                url = f"https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={self.api_key}"
                resp = self._session.get(url, timeout=1.0)
                if resp.status_code == 200:
                    data = resp.json()
                    bullish_pct = data.get("sentiment", {}).get("bullishPercent", 0.5)
                    score = round((bullish_pct - 0.5) * 2.0, 2)
                    self._sentiment_cache[symbol] = (now, score)
                    return score
                elif resp.status_code in (401, 403, 429):
                    # Finnhub news-sentiment is not available on standard/free tier — disable to prevent lag
                    self._finnhub_sentiment_disabled = True
            except Exception:
                pass
        
        # 2. Mathematical momentum-derived sentiment (deterministic)
        hist = self.history_windows.get(symbol, [100.0])
        if len(hist) > 10:
            denom = hist[-10]
            if abs(denom) > 1e-12:
                ret = (hist[-1] - denom) / denom
            else:
                ret = 0.0
            sentiment = math.tanh(ret * 20.0)
            score = round(max(-1.0, min(1.0, sentiment)), 2)
        else:
            score = 0.0

        self._sentiment_cache[symbol] = (now, score)
        return score
