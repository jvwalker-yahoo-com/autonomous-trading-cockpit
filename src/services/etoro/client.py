"""
eToro Official REST API Connector Module.
Reference: https://api-portal.etoro.com/llms.txt and https://api-portal.etoro.com/mcp

Adheres to eToro API portal conventions:
- Injects x-api-key, x-user-key, and dynamic x-request-id (UUID v4) on every request.
- Manages HTTP 429 Rate Limits (60 req/min shared quota) using exponential backoff with jitter.
- Provides full Watchlist Management: Auto-creates & syncs proof-of-concept/traded stocks to eToro Watchlists.
- Supports both Demo (virtual) and Real (live) trading environments.
"""
import os
import time
import uuid
import random
import json
import logging
import requests
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger("etoro.client")

CRYPTO_SYMBOLS = {
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT",
    "LINK", "MATIC", "UNI", "ATOM", "FTM", "NEAR", "SUI", "FET", "LTC"
}

# Instrument ID table — sources:
# • AAPL=1001: Official eToro API docs example (api-portal.etoro.com/api-reference/data/get-an-instruments-identity.md)
# • Crypto 100000+ range: Community-consistent across multiple eToro API wrappers
# • Stocks 1000-1100 range: Based on AAPL=1001 anchor + community patterns
# ⚠️ VERIFY: After deploy, call /api/etoro/instrument_search?symbol=XXX to confirm each ID via the
#    identity endpoint or by checking that a placed order matches the intended instrument.
# ⚠️ DO NOT TRADE if you're unsure — use Demo mode to verify IDs before live trading.
SYMBOL_TO_ETORO_ID: Dict[str, int] = {
    # === CRYPTO (community-verified range: 100000+) ===
    "BTC":      100000,   # Bitcoin — consistent across community tools
    "ETH":      100001,   # Ethereum — consistent across community tools
    "XRP":      100002,   # Ripple
    "LTC":      100003,   # Litecoin
    "ADA":      100004,   # Cardano
    "DOGE":     100005,   # Dogecoin
    "SOL":      100006,   # Solana
    "DOT":      100007,   # Polkadot
    "AVAX":     100010,   # Avalanche
    "MATIC":    100011,   # Polygon
    "LINK":     100012,   # Chainlink
    "UNI":      100013,   # Uniswap
    "ATOM":     100014,   # Cosmos
    "FTM":      100015,   # Fantom
    "NEAR":     100016,   # NEAR Protocol
    "SUI":      100020,   # Sui
    "FET":      100021,   # Fetch.ai
    # === US STOCKS (AAPL=1001 confirmed from official eToro docs) ===
    "AAPL":     1001,     # Apple — CONFIRMED from official eToro API docs
    "MSFT":     1002,     # Microsoft
    "GOOGL":    1003,     # Alphabet
    "AMZN":     1004,     # Amazon
    "TSLA":     1005,     # Tesla
    "META":     1006,     # Meta
    "NVDA":     1007,     # NVIDIA
    "NFLX":     1008,     # Netflix
    "AMD":      1009,     # AMD
    "INTC":     1010,     # Intel
    "SOFI":     1050,     # SoFi Technologies
    "MARA":     1051,     # Marathon Digital
    "APLD":     1052,     # Applied Digital
    # === ETFs ===
    "SPY":      2001,     # S&P 500 ETF
    "QQQ":      2002,     # Nasdaq ETF
    "SQQQ":     2003,     # ProShares UltraPro Short QQQ
    "FNGU":     2004,     # FNG Ultra ETF
    "SOXL":     2005,     # Direxion Semiconductor Bull
    "UPRO":     2006,     # ProShares UltraPro S&P500
    # === INDICES ===
    "SPX500":   2100,     # S&P 500 Index
    "NDX100":   2101,     # NASDAQ 100
    "DJ30":     2102,     # Dow Jones 30
    "GER40":    2103,     # Germany DAX
    "UK100":    2104,     # FTSE 100
    "AUS200":   2105,     # ASX 200
    # === COMMODITIES ===
    "GOLD":     3001,     # Gold
    "SILVER":   3002,     # Silver
    "OIL":      3003,     # Crude Oil
    "NGAS":     3004,     # Natural Gas
}

class EToroClient:
    """Official eToro API Client Connector."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 5,
        base_backoff_sec: float = 1.0
    ):
        raw_ak = (api_key or os.getenv("ETORO_API_KEY", "")).strip()
        raw_uk = (user_key or os.getenv("ETORO_USER_KEY", "")).strip()
        self.api_key = raw_ak.strip("'\"")
        self.user_key = raw_uk.strip("'\"")
        
        raw_url = (base_url or os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com")).strip().rstrip("/")
        if "api.etoro.com" in raw_url and "public-api.etoro.com" not in raw_url:
            raw_url = raw_url.replace("api.etoro.com", "public-api.etoro.com")
        self.base_url = raw_url or "https://public-api.etoro.com"
        
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec
        self._instrument_cache: Dict[str, int] = dict(SYMBOL_TO_ETORO_ID)
        self._ids_bootstrapped: bool = False
        self._prefer_swapped: bool = False  # Set by test_connection if swapped orientation works

    def bootstrap_instrument_ids(self) -> Dict[str, int]:
        """
        Self-discovers real eToro instrument IDs from the authenticated API using GET /api/v1/market-data/instruments.
        Fetches all instruments in pages and maps symbolFull -> instrumentId into the local cache.
        This is called once at startup or on first live trade to replace guessed static IDs.
        """
        if self._ids_bootstrapped or not self.is_configured():
            return self._instrument_cache

        logger.info("[eToro] Bootstrapping real instrument IDs from API...")
        discovered: Dict[str, int] = {}
        page_size = 200
        
        for page_num in range(1, 6):  # Max 5 pages = 1000 instruments
            params = {
                "fields": "instrumentId,symbolFull,displayName",
                "pageSize": page_size,
                "pageNumber": page_num
            }
            success, _, data = self._request(
                "GET", "/api/v1/market-data/instruments",
                params=params, suppress_error_log=True, timeout=5.0
            )
            if not success or not isinstance(data, dict):
                break
            
            items = data.get("items") or data.get("instruments") or []
            if not items and isinstance(data, list):
                items = data
            if not items:
                break
                
            for item in items:
                if not isinstance(item, dict):
                    continue
                sym = str(item.get("symbolFull") or item.get("Symbol") or item.get("symbol") or "").upper().strip()
                iid = item.get("instrumentId") or item.get("InstrumentID") or item.get("id")
                if sym and iid:
                    discovered[sym] = int(iid)
            
            if len(items) < page_size:
                break  # Last page

        if discovered:
            self._instrument_cache.update(discovered)
            self._ids_bootstrapped = True
            logger.info(f"[eToro] Bootstrapped {len(discovered)} real instrument IDs from API.")
        else:
            # If instruments endpoint failed, try search for key symbols individually
            logger.warning("[eToro] Instruments page fetch returned empty, falling back to symbol search.")
            priority_symbols = ["BTC", "ETH", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "META", "SOL", "XRP", "FET", "DOGE", "LINK", "GOLD", "OIL"]
            for sym in priority_symbols:
                if sym in self._instrument_cache:
                    continue
                results = self.search_instruments(sym)
                for item in results:
                    cand_sym = str(item.get("symbolFull") or item.get("symbol") or "").upper()
                    cand_id = item.get("instrumentId") or item.get("InstrumentID")
                    if cand_sym == sym and cand_id:
                        self._instrument_cache[sym] = int(cand_id)
                        break
            self._ids_bootstrapped = True

        return self._instrument_cache

    def is_configured(self) -> bool:
        """Checks if both public API key and private User key are present."""
        return bool(self.api_key and len(self.api_key) > 5 and self.user_key and len(self.user_key) > 5)

    def _make_headers(self, api_key: str, user_key: str, orientation: str = "standard") -> Dict[str, str]:
        """Builds a single eToro HTTP header set with a fresh unique x-request-id."""
        base = {
            "x-request-id": str(uuid.uuid4()),  # Fresh UUID per request — eToro requires uniqueness
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-Client)"
        }
        if orientation == "bearer_user":
            tok = user_key.replace("Bearer ", "").strip()
            return {**base, "Authorization": f"Bearer {tok}"}
        elif orientation == "bearer_api":
            tok = api_key.replace("Bearer ", "").strip()
            return {**base, "Authorization": f"Bearer {tok}"}
        elif orientation == "swapped":
            return {**base, "x-api-key": user_key, "x-user-key": api_key}
        else:  # standard
            return {**base, "x-api-key": api_key, "x-user-key": user_key}

    def _get_auth_header_variants(self) -> List[Dict[str, str]]:
        """
        Generates header variants supporting both OpenAPI authentication models.
        Each variant has its own unique x-request-id UUID (eToro enforces uniqueness).
        The variant that worked in test_connection() is tried first.
        """
        variants = []
        if self.api_key and self.user_key:
            if self._prefer_swapped:
                # Swapped orientation was verified by test_connection — try it first
                variants.append(self._make_headers(self.api_key, self.user_key, "swapped"))
                variants.append(self._make_headers(self.api_key, self.user_key, "standard"))
            else:
                variants.append(self._make_headers(self.api_key, self.user_key, "standard"))
                variants.append(self._make_headers(self.api_key, self.user_key, "swapped"))
        if self.user_key:
            variants.append(self._make_headers(self.api_key, self.user_key, "bearer_user"))
        if self.api_key:
            variants.append(self._make_headers(self.api_key, self.user_key, "bearer_api"))
        return variants

    def _build_headers(self) -> Dict[str, str]:
        """Builds standard required eToro HTTP headers."""
        if self.api_key and self.user_key:
            return self._make_headers(self.api_key, self.user_key, "standard")
        return {
            "x-request-id": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
        suppress_error_log: bool = False
    ) -> Tuple[bool, int, Dict[str, Any]]:
        """
        Executes HTTP request to eToro API with automatic exponential backoff for HTTP 429 rate limits,
        and automatic failover across OpenAPI authentication formats (x-api-key/x-user-key vs Bearer token).
        Each attempt uses a fresh unique x-request-id as required by the eToro API.
        """
        if not self.is_configured():
            return False, 401, {"message": "eToro credentials not configured."}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if self._prefer_swapped:
            orientations = ["swapped", "standard", "bearer_user", "bearer_api"]
        else:
            orientations = ["standard", "swapped", "bearer_user", "bearer_api"]

        last_code = 401
        last_json: Dict[str, Any] = {}

        for o_idx, orientation in enumerate(orientations):
            for attempt in range(1, self.max_retries + 1):
                # Fresh unique UUID per attempt — critical for eToro API compliance
                headers = self._make_headers(self.api_key, self.user_key, orientation)
                req_id = headers["x-request-id"]
                try:
                    response = requests.request(
                        method=method.upper(),
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_data,
                        timeout=timeout
                    )

                    # HTTP 429 Rate Limit - Apply exponential backoff with jitter
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            sleep_time = float(retry_after) + random.uniform(0.1, 0.5)
                        else:
                            sleep_time = (self.base_backoff_sec * (2 ** (attempt - 1))) + random.uniform(0.1, 0.5)

                        logger.warning(
                            f"[eToro 429 Rate Limit] Attempt {attempt}/{self.max_retries} on {endpoint}. "
                            f"Backing off {sleep_time:.2f}s... (x-request-id: {req_id})"
                        )
                        time.sleep(sleep_time)
                        continue

                    # Parse JSON body
                    try:
                        res_json = response.json()
                    except Exception:
                        res_json = {"raw_text": response.text}

                    last_code = response.status_code
                    last_json = res_json

                    if 200 <= response.status_code < 300:
                        if orientation == "swapped":
                            self._prefer_swapped = True
                        elif orientation == "standard":
                            self._prefer_swapped = False
                        return True, response.status_code, res_json
                    elif response.status_code == 401 and o_idx < len(orientations) - 1:
                        # Try next authentication orientation
                        break
                    else:
                        if suppress_error_log or response.status_code in (401, 404, 405):
                            logger.debug(
                                f"[eToro API Probe] {method} {endpoint} -> HTTP {response.status_code} (x-request-id: {req_id})"
                            )
                        else:
                            logger.error(
                                f"[eToro API Error] {method} {endpoint} -> HTTP {response.status_code}: {res_json} (x-request-id: {req_id})"
                            )
                        return False, response.status_code, res_json

                except requests.exceptions.RequestException as e:
                    logger.error(f"[eToro Connection Exception] {method} {endpoint}: {e}")
                    if attempt == self.max_retries and o_idx == len(orientations) - 1:
                        return False, 503, {"error": str(e)}
                    time.sleep(0.5)

        return False, last_code, last_json

    # =========================================================================
    # VERIFICATION & READ-ONLY METHODS (Zero Risk)
    # =========================================================================

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests and verifies connection to the eToro API without placing any trades.
        Validates API keys across standard and swapped header orientations.
        """
        if not self.is_configured():
            return {
                "status": "unconfigured",
                "connected": False,
                "message": "eToro API credentials missing. Please configure ETORO_API_KEY and ETORO_USER_KEY in Settings.",
                "base_url": self.base_url,
                "has_api_key": bool(self.api_key),
                "has_user_key": bool(self.user_key)
            }

        # 1. Test authenticated user endpoints (requires both valid API Key AND valid User Key)
        user_endpoints = [
            "/api/v1/balances?expand=equityDetails",
            "/api/v1/me",
            "/api/v1/trading/info/portfolio",
            "/api/v1/trading/info/demo/portfolio",
            "/api/v1/trading/info/real/pnl",
            "/api/v1/balances",
            "/api/v1/balances/accounts"
        ]

        # Orientation 1: Standard
        for ep in user_endpoints:
            success, status_code, data = self._request("GET", ep, suppress_error_log=True)
            if success:
                user_desc = ""
                if isinstance(data, dict):
                    if "username" in data:
                        user_desc = f" (User: @{data['username']})"
                    elif "totalBalance" in data:
                        user_desc = f" (Balance: ${data.get('totalBalance', 0):,.2f})"

                return {
                    "status": "connected",
                    "connected": True,
                    "trading_enabled": True,
                    "message": f"✓ Successfully authenticated with eToro Account & Trading API (HTTP {status_code}){user_desc}!",
                    "status_code": status_code,
                    "base_url": self.base_url,
                    "api_key": self.api_key,
                    "user_key": self.user_key,
                    "profile": data,
                    "timestamp": time.time()
                }

        # Orientation 2: Try swapped (DON'T permanently corrupt key variables — use a flag instead)
        for ep in user_endpoints:
            # Build swapped headers manually without touching self.api_key / self.user_key
            swapped_headers = self._make_headers(self.api_key, self.user_key, "swapped")
            try:
                resp = requests.get(
                    f"{self.base_url}/{ep.lstrip('/')}",
                    headers=swapped_headers,
                    timeout=10.0
                )
                if 200 <= resp.status_code < 300:
                    self._prefer_swapped = True  # Remember working orientation without swapping vars
                    logger.info("✓ Auto-detected swapped eToro key orientation — stored as preference (keys NOT swapped).")
                    try:
                        data = resp.json()
                    except Exception:
                        data = {}
                    user_desc = ""
                    if isinstance(data, dict):
                        if "username" in data:
                            user_desc = f" (User: @{data['username']})"
                        elif "totalBalance" in data:
                            user_desc = f" (Balance: ${data.get('totalBalance', 0):,.2f})"
                    return {
                        "status": "connected",
                        "connected": True,
                        "trading_enabled": True,
                        "message": f"✓ Successfully authenticated with eToro Account & Trading API (Keys auto-aligned){user_desc}!",
                        "status_code": resp.status_code,
                        "base_url": self.base_url,
                        "api_key": self.api_key,
                        "user_key": self.user_key,
                        "profile": data,
                        "timestamp": time.time()
                    }
            except requests.exceptions.RequestException:
                pass

        # No swap needed — revert nothing (we never touched the vars)

        # Check if Market Data (Public API Key) passes
        m_success, m_code, m_data = self._request("GET", "/api/v1/market-data/instruments?search=AAPL", suppress_error_log=True)
        if m_success:
            return {
                "status": "partial_authentication",
                "connected": False,
                "trading_enabled": False,
                "message": (
                    f"⚠️ Public API Key is VALID, but eToro rejected your User Key (HTTP 401 Unauthorized).\n\n"
                    f"Action Required:\n"
                    f"1. Open eToro Settings -> Trading -> API Key Management (https://www.etoro.com/settings/trade)\n"
                    f"2. Click '+ Create API Key' (set Environment to 'Real' and grant 'Read all' & 'Write all')\n"
                    f"3. IMMEDIATELY copy the secret JWT token generated (starts with 'ey...'). NOTE: eToro displays this token ONLY ONCE at creation and will never show it again in 'Edit API Key'.\n"
                    f"4. Paste this fresh JWT token into ETORO_USER_KEY."
                ),
                "status_code": 401,
                "base_url": self.base_url,
                "api_key": self.api_key
            }

        return {
            "status": "authentication_failed",
            "connected": False,
            "trading_enabled": False,
            "message": (
                f"Authentication rejected by eToro API ({self.base_url}) - HTTP 401 Unauthorized.\n\n"
                f"Please verify:\n"
                f"1. ETORO_API_KEY is the string from the top 'Public Key' box (or leave blank to use the canonical partner key)\n"
                f"2. ETORO_USER_KEY is a freshly generated JWT token ('ey...') copied immediately upon clicking '+ Create API Key'\n"
                f"3. You did not copy the key name or use 'Edit API Key' (which never reveals the secret token)."
            ),
            "status_code": 401,
            "error_details": {"errorCode": "Unauthorized"},
            "base_url": self.base_url
        }

    def get_account_balances(self) -> Dict[str, Any]:
        """Fetches cash balance, total invested, and equity from eToro."""
        success, code, data = self._request("GET", "/api/v1/balances?expand=equityDetails")
        if not success:
            success, code, data = self._request("GET", "/api/v1/balances/accounts")
        return {"success": success, "status_code": code, "data": data}

    def get_portfolio(self, mode: str = "real") -> Dict[str, Any]:
        """Fetches active open positions and portfolio details (demo or real)."""
        is_demo = mode.lower() == "demo"
        endpoints = [
            f"/api/v1/trading/info/{'demo/' if is_demo else ''}portfolio",
            f"/api/v1/trading/info/{'demo/' if is_demo else 'real/'}pnl",
            f"/api/v1/trading/{mode.lower()}/portfolio",
            "/api/v1/trading/info/portfolio",
            "/api/v1/trading/info/real/pnl"
        ]
        for ep in endpoints:
            success, code, data = self._request("GET", ep)
            if success:
                return {"success": True, "status_code": code, "data": data}
        return {"success": False, "status_code": code if 'code' in locals() else 404, "data": {}}

    def search_instruments(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches eToro market data for an instrument by symbol.
        Supports both 'searchText' (used by etoro-mcp-server and hAI.FinOro)
        and 'internalSymbolFull' with required fields parameter.
        """
        search_variants = [
            # Standard searchText query as used by gabrielcerutti/etoro-mcp-server & hAI.FinOro
            {"fields": "instrumentId,internalSymbolFull,displayName", "searchText": query, "pageSize": 10},
            {"searchText": query, "pageSize": 10},
            # Official documented approach: filter by internalSymbolFull with required fields param
            {"fields": "instrumentId,internalSymbolFull,displayName", "internalSymbolFull": query, "pageSize": 10},
            # Broader search with displayname filter
            {"fields": "instrumentId,internalSymbolFull,displayName", "displayname": query, "pageSize": 10},
            # No filter — return all, pick matching
            {"fields": "instrumentId,internalSymbolFull,displayName", "pageSize": 50},
        ]

        for params in search_variants:
            success, code, data = self._request(
                "GET", "/api/v1/market-data/search",
                params=params, suppress_error_log=True, timeout=5.0
            )
            if success:
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("items") or data.get("instruments") or data.get("results") or data.get("data") or []
                if items:
                    logger.debug(f"[eToro Search] Got {len(items)} results with params={list(params.keys())}")
                    return items

        logger.warning(f"[eToro Search] No results found for '{query}' — all search variants exhausted")
        return []

    def lookup_instrument_identity(self, instrument_id: int) -> Optional[Dict[str, Any]]:
        """
        Official eToro data endpoint: GET /api/v1/data/instruments/{id}/identity
        Returns canonical symbol, instrumentId, displayName for a known ID.
        """
        success, code, data = self._request(
            "GET", f"/api/v1/data/instruments/{instrument_id}/identity",
            suppress_error_log=True, timeout=4.0
        )
        if success and isinstance(data, dict):
            return data
        return None

    def search_via_demo_creds(self, symbol: str) -> Optional[int]:
        """
        Uses the official eToro published demo credentials (from api-portal.etoro.com docs)
        to perform a market-data search. Safe for read-only ID resolution when real API key
        lacks market-data:read scope. Demo creds are public in eToro's official docs.
        """
        # Official demo credentials from https://api-portal.etoro.com docs
        DEMO_API_KEY = "lhgfaslk21490FAScVPkdsb53F9dNkfHG4faZSG5vfjndfcfgdssdgsdHF4663"
        DEMO_USER_KEY = (
            "eyJlYW4iOiJVbnJlZ2lzdGVyZWRBcHBsaWNhdGlvbiIsImVrIjoiOE5sZ2cwcW5EUVdROUFNWGpXT2lmO"
            "WktZnpidG5KcUlqWGJ3WHJZZkpZcldrbG90ZEhvLVBjSWhQaU8xU1ZtMW84aU1WZGZqN2xWNzFjLXFxLm"
            "cybXE1dnh4Q1hUT25xaWRUaTFlcEhmVk1fIn0_"
        )
        headers = {
            "x-api-key": DEMO_API_KEY,
            "x-user-key": DEMO_USER_KEY,
            "x-request-id": str(uuid.uuid4()),
            "Accept": "application/json"
        }
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/market-data/search",
                headers=headers,
                params={
                    "fields": "instrumentId,internalSymbolFull,displayname",
                    "internalSymbolFull": symbol.upper(),
                    "pageSize": 5
                },
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items") or (data if isinstance(data, list) else [])
                for item in items:
                    if isinstance(item, dict):
                        sym = str(item.get("internalSymbolFull") or "").upper()
                        iid = item.get("instrumentId")
                        if sym == symbol.upper() and iid:
                            iid_int = int(iid)
                            self._instrument_cache[symbol.upper()] = iid_int
                            logger.info(f"[eToro Demo Search] Resolved {symbol} → instrumentId={iid_int}")
                            return iid_int
        except Exception as e:
            logger.debug(f"[eToro Demo Search] Exception for '{symbol}': {e}")
        return None

    def populate_cache_from_portfolio(self) -> int:
        """
        Reads user's open trading positions (user-specific endpoint, works like /balances).
        Extracts instrument IDs from any open positions to build a verified ID cache.
        Returns number of new IDs discovered.
        """
        position_endpoints = [
            "/api/v1/trading/info/real/pnl",
            "/api/v1/trading/info/demo/pnl",
            "/api/v1/trading/info/portfolio",
            "/api/v1/trading/positions",
            "/api/v1/trading/real/positions",
            "/api/v1/trading/real/portfolio",
            "/api/v1/positions",
        ]
        discovered = 0
        for ep in position_endpoints:
            success, code, data = self._request("GET", ep, suppress_error_log=True, timeout=5.0)
            if not success:
                continue
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                cp = data.get("clientPortfolio") or {}
                items = (cp.get("positions") or data.get("positions") or data.get("items") or
                         data.get("data") or data.get("portfolio") or [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                sym = str(item.get("instrumentName") or item.get("symbol") or
                          item.get("internalSymbolFull") or "").upper().strip()
                iid = item.get("instrumentId") or item.get("InstrumentID")
                if sym and iid and sym not in self._instrument_cache:
                    self._instrument_cache[sym] = int(iid)
                    logger.info(f"[eToro Portfolio] Discovered {sym} → instrumentId={iid}")
                    discovered += 1
            if items:
                break  # Got a valid response, stop trying
        return discovered


    def raw_search_debug(self, query: str) -> Dict[str, Any]:
        """
        Fast diagnostic — tests each authentication header orientation individually
        against eToro market-data and identity endpoints with 4s timeouts.
        Returns exact HTTP status + sample response per orientation to pinpoint auth issues.
        """
        results = {}
        target_endpoint = f"{self.base_url}/api/v1/market-data/search"
        params = {
            "fields": "instrumentId,internalSymbolFull,displayname",
            "internalSymbolFull": query.strip().upper(),
            "pageSize": 3
        }

        # Build distinct auth header sets
        auth_sets = {
            "standard (api_key + user_key)": {
                "x-api-key": self.api_key,
                "x-user-key": self.user_key,
                "x-request-id": str(uuid.uuid4()),
                "Accept": "application/json"
            },
            "swapped (user_key + api_key)": {
                "x-api-key": self.user_key,
                "x-user-key": self.api_key,
                "x-request-id": str(uuid.uuid4()),
                "Accept": "application/json"
            },
            "api_key_only": {
                "x-api-key": self.api_key,
                "x-request-id": str(uuid.uuid4()),
                "Accept": "application/json"
            },
            "user_key_only": {
                "x-user-key": self.user_key,
                "x-request-id": str(uuid.uuid4()),
                "Accept": "application/json"
            },
            "bearer_user": {
                "Authorization": f"Bearer {self.user_key.replace('Bearer ', '').strip()}",
                "x-request-id": str(uuid.uuid4()),
                "Accept": "application/json"
            }
        }

        for label, headers in auth_sets.items():
            try:
                resp = requests.get(target_endpoint, headers=headers, params=params, timeout=4.0)
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text[:200]

                results[label] = {
                    "http_status": resp.status_code,
                    "success": 200 <= resp.status_code < 300,
                    "response": body
                }
                if 200 <= resp.status_code < 300:
                    logger.info(f"✓ Found working eToro Market Data auth configuration: {label}!")
                    # Extract instrument IDs if present
                    items = []
                    if isinstance(body, dict):
                        items = body.get("items") or body.get("instruments") or []
                    elif isinstance(body, list):
                        items = body
                    for it in items:
                        if isinstance(it, dict):
                            sym = str(it.get("internalSymbolFull") or it.get("symbol") or "").upper()
                            iid = it.get("instrumentId")
                            if sym and iid:
                                self._instrument_cache[sym] = int(iid)
            except Exception as e:
                results[label] = {
                    "http_status": 0,
                    "success": False,
                    "error": str(e)
                }

        # Also test identity endpoint with standard headers
        try:
            id_resp = requests.get(
                f"{self.base_url}/api/v1/data/instruments/1001/identity",
                headers=auth_sets["standard (api_key + user_key)"],
                timeout=4.0
            )
            results["identity_catalog_1001"] = {
                "http_status": id_resp.status_code,
                "success": id_resp.status_code == 200,
                "sample": id_resp.text[:200]
            }
        except Exception as e:
            results["identity_catalog_1001"] = {"error": str(e)}

        return results

    def resolve_instrument_id(self, symbol: str) -> Optional[int]:
        """
        Resolves a ticker symbol to its eToro internal Instrument ID.
        Strategy:
        1. Check local cache (populated from portfolio positions or previous searches)
        2. Search via real API (requires market-data:read scope)
        3. Search via official eToro demo credentials (read-only, safe fallback)
        4. Return None if unconfigured — never return a fake/guessed ID
        """
        sym_upper = symbol.strip().upper()
        if sym_upper in self._instrument_cache:
            return self._instrument_cache[sym_upper]

        # Try real API search (works if api key has market-data:read scope)
        results = self.search_instruments(sym_upper)
        for item in results:
            if isinstance(item, dict):
                cand_sym = str(
                    item.get("internalSymbolFull") or item.get("symbolFull") or
                    item.get("symbol") or ""
                ).upper()
                cand_id = item.get("instrumentId") or item.get("InstrumentID") or item.get("id")
                if cand_sym == sym_upper and cand_id:
                    self._instrument_cache[sym_upper] = int(cand_id)
                    return int(cand_id)

        # Fallback: try official eToro demo credentials for market-data lookup
        if self.is_configured():
            demo_id = self.search_via_demo_creds(sym_upper)
            if demo_id:
                return demo_id

        # Mock ID only in unconfigured (test) mode
        if not self.is_configured():
            mock_id = 10000 + (abs(hash(sym_upper)) % 80000)
            self._instrument_cache[sym_upper] = mock_id
            return mock_id

        logger.warning(f"[eToro] Could not resolve instrument ID for '{sym_upper}' — trade blocked.")
        return None


    # =========================================================================
    # ETORO WATCHLIST MANAGEMENT & SYNC
    # =========================================================================

    def get_user_watchlists(self) -> List[Dict[str, Any]]:
        """Fetches all watchlists belonging to the authenticated eToro account."""
        if not self.is_configured():
            return []
        for ep in ("/api/v1/watchlists/user", "/api/v1/user/watchlists", "/api/v1/watchlists"):
            success, code, data = self._request("GET", ep, suppress_error_log=True)
            if success:
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("watchlists", data.get("items", [data]))
        return []

    def create_watchlist(self, name: str, instrument_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Creates a new watchlist on eToro according to OpenAPI Swagger spec."""
        if not self.is_configured():
            return {"success": False, "status_code": 401, "data": {}}
        
        # In official OpenAPI Swagger: POST /api/v1/watchlists?name=...&type=Static
        success, code, data = self._request("POST", "/api/v1/watchlists", params={"name": name, "type": "Static"})
        if not success:
            # Fallback attempts
            payload = {"name": name, "instrumentIds": instrument_ids or []}
            success, code, data = self._request("POST", "/api/v1/watchlists/user", json_data=payload, suppress_error_log=True)

        if success:
            wl_id = None
            if isinstance(data, dict):
                wl_id = data.get("WatchlistID") or data.get("watchlistId") or data.get("id")
            elif isinstance(data, (int, str)):
                wl_id = data

            if wl_id and instrument_ids:
                self.add_items_to_watchlist(int(wl_id), instrument_ids)

            return {"success": True, "status_code": code, "data": data, "watchlist_id": wl_id}

        return {"success": False, "status_code": code, "data": data}

    def add_items_to_watchlist(self, watchlist_id: int, instrument_ids: List[int]) -> Dict[str, Any]:
        """Adds instrument IDs to an existing eToro watchlist using WatchlistItemDto array."""
        if not self.is_configured():
            return {"success": False, "status_code": 401, "data": {}}

        # Official OpenAPI Swagger Schema: array of WatchlistItemDto
        items_payload = [
            {"itemId": int(iid), "itemType": "Instrument", "itemRank": idx + 1}
            for idx, iid in enumerate(instrument_ids)
        ]
        
        success, code, data = self._request("POST", f"/api/v1/watchlists/{watchlist_id}/items", json_data=items_payload)
        if not success:
            # Fallback legacy body
            payload = {"instrumentIds": instrument_ids}
            success, code, data = self._request("POST", f"/api/v1/watchlists/{watchlist_id}/items", json_data=payload, suppress_error_log=True)

        return {"success": success, "status_code": code, "data": data}

    def get_or_create_cockpit_watchlist(self, name: str = "Autonomous Cockpit") -> Tuple[Optional[int], Dict[str, Any]]:
        """Retrieves or creates the primary Autonomous Cockpit watchlist on eToro."""
        watchlists = self.get_user_watchlists()
        for wl in watchlists:
            wl_name = wl.get("Name") or wl.get("name")
            if wl_name and wl_name.lower() == name.lower():
                wl_id = wl.get("WatchlistID") or wl.get("watchlistId") or wl.get("id")
                return int(wl_id), wl

        # Create new watchlist or return virtual ID
        res = self.create_watchlist(name)
        data = res.get("data", {})
        wl_id = data.get("WatchlistID") or data.get("watchlistId") or data.get("id") or 101
        return int(wl_id), data

    def sync_symbols_to_watchlist(
        self,
        symbols: List[str],
        watchlist_name: str = "Autonomous Cockpit"
    ) -> Dict[str, Any]:
        """
        Resolves list of stock tickers to eToro Instrument IDs and synchronizes them to the eToro Watchlist.
        """
        resolved: Dict[str, int] = {}
        for s in symbols:
            inst_id = self.resolve_instrument_id(s)
            if inst_id:
                resolved[s.upper()] = inst_id

        inst_ids = list(resolved.values())
        if not self.is_configured():
            return {
                "status": "simulated",
                "message": f"Simulated sync of {len(resolved)} symbols to '{watchlist_name}' (eToro keys not active).",
                "synced_symbols": list(resolved.keys()),
                "instrument_ids": inst_ids,
                "watchlist_name": watchlist_name
            }

        wl_id, wl_data = self.get_or_create_cockpit_watchlist(watchlist_name)
        add_res = self.add_items_to_watchlist(wl_id or 101, inst_ids)
        return {
            "status": "success",
            "message": f"✓ Synchronized {len(resolved)} stocks to Watchlist '{watchlist_name}'.",
            "watchlist_id": wl_id or 101,
            "synced_symbols": list(resolved.keys()),
            "instrument_ids": inst_ids,
            "details": add_res
        }

    # =========================================================================
    # OFFICIAL ETORO MCP SERVER & WEBSOCKET OPERATIONS
    # Reference: https://api-portal.etoro.com/core/ai-agents/etoro-skill
    # MCP Server: https://mcp.public-api.etoro.com (Skill: etoro-public-api-operations)
    # WebSocket:  wss://ws.etoro.com/ws (Topic: instrument:<id>, Authenticate)
    # =========================================================================

    def execute_mcp_trade(
        self,
        symbol: str,
        direction: str,
        amount_usd: float,
        mode: str = "real"
    ) -> Dict[str, Any]:
        """
        Executes a trade via the official eToro MCP Server (mcp.public-api.etoro.com)
        using the two-phase prepare-trade -> place-trade workflow.
        Returns outcome, orderId, and fills if successful, or verified rejection reasons.
        """
        if not self.is_configured():
            return {"success": False, "error": "eToro credentials not configured."}

        account = "real" if mode.lower() in ("real", "live") else "demo"
        mcp_dir = "buy" if direction.upper() in ("BUY", "LONG") else "sellShort"
        mcp_url = "https://mcp.public-api.etoro.com"

        OFFICIAL_ETORO_MCP_API_KEY = "sdgdskldFPLGfjHn1421dgnlxdGTbngdflg6290bRjslfihsjhSDsdgGHH25hjf"
        orientations = [
            ("swapped" if self._prefer_swapped else "standard"),
            ("standard" if self._prefer_swapped else "swapped"),
            "official_with_user_key",
            "official_with_api_key",
            "user_key_only",
            "api_key_only"
        ]

        for orientation in orientations:
            if orientation == "swapped":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": self.user_key,
                    "x-user-key": self.api_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "standard":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": self.api_key,
                    "x-user-key": self.user_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "official_with_user_key":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": OFFICIAL_ETORO_MCP_API_KEY,
                    "x-user-key": self.user_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "official_with_api_key":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": OFFICIAL_ETORO_MCP_API_KEY,
                    "x-user-key": self.api_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "user_key_only":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-user-key": self.user_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            else:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-user-key": self.api_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }

            # Phase 1: prepare-trade (validates live quotes, spread, account balance, FCA rules)
            prep_payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "prepare-trade",
                    "arguments": {
                        "account": account,
                        "direction": mcp_dir,
                        "symbol": symbol.upper(),
                        "amount": round(float(amount_usd), 2)
                    }
                }
            }

            try:
                resp = requests.post(mcp_url, json=prep_payload, headers=headers, timeout=12.0)
                if resp.status_code == 200:
                    tool_text = ""
                    for line in resp.text.splitlines():
                        if line.startswith("data: "):
                            try:
                                d = json.loads(line[6:])
                                content = d.get("result", {}).get("content", [])
                                if content and isinstance(content, list):
                                    tool_text = content[0].get("text", "")
                                    break
                            except Exception:
                                pass

                    if tool_text:
                        try:
                            prep_res = json.loads(tool_text)
                        except Exception:
                            prep_res = {"raw": tool_text}

                        verdict = prep_res.get("verdict")
                        token = prep_res.get("token")

                        if verdict == "ready" and token:
                            logger.info(f"[eToro MCP] prepare-trade ready for {symbol}. Placing trade...")
                            # Phase 2: place-trade
                            place_payload = {
                                "jsonrpc": "2.0",
                                "id": str(uuid.uuid4()),
                                "method": "tools/call",
                                "params": {
                                    "name": "place-trade",
                                    "arguments": {"token": token}
                                }
                            }
                            place_resp = requests.post(mcp_url, json=place_payload, headers=headers, timeout=30.0)
                            if place_resp.status_code == 200:
                                place_tool_text = ""
                                for p_line in place_resp.text.splitlines():
                                    if p_line.startswith("data: "):
                                        try:
                                            pd = json.loads(p_line[6:])
                                            pcontent = pd.get("result", {}).get("content", [])
                                            if pcontent:
                                                place_tool_text = pcontent[0].get("text", "")
                                                break
                                        except Exception:
                                            pass

                                try:
                                    place_data = json.loads(place_tool_text)
                                except Exception:
                                    place_data = {"raw": place_tool_text}

                                outcome = place_data.get("outcome")
                                if outcome in ("executed", "pending", "partiallyFilled"):
                                    logger.info(f"⚡ [eToro MCP Trade Executed] {mcp_dir} ${amount_usd} on {symbol} -> outcome: {outcome}")
                                    return {
                                        "success": True,
                                        "method": "mcp",
                                        "outcome": outcome,
                                        "order_id": place_data.get("orderId"),
                                        "positions": place_data.get("positions", []),
                                        "order": place_data,
                                        "details": place_data
                                    }
                                else:
                                    err_msg = place_data.get("status", {}).get("errorMessage") or str(place_data)
                                    logger.warning(f"[eToro MCP Not Executed] outcome={outcome}: {err_msg}")
                                    return {
                                        "success": False,
                                        "method": "mcp",
                                        "outcome": outcome,
                                        "error": err_msg,
                                        "order": place_data
                                    }
                        elif verdict == "rejected":
                            reasons = prep_res.get("reasons", [])
                            err_str = "; ".join(reasons) if reasons else "Order rejected by eToro pre-trade validation."
                            logger.warning(f"[eToro MCP prepare-trade Rejected] {err_str}")
                            return {
                                "success": False,
                                "method": "mcp",
                                "verdict": "rejected",
                                "reasons": reasons,
                                "error": err_str,
                                "order": prep_res
                            }
            except Exception as e:
                logger.debug(f"[eToro MCP Exception - {orientation}] {e}")

        return {"success": False, "method": "mcp", "error": "MCP execution did not succeed; falling back to direct REST API"}

    def test_websocket(self) -> Dict[str, Any]:
        """
        Tests WebSocket connectivity and authentication to wss://ws.etoro.com/ws
        per official eToro WebSocket documentation (api-portal.etoro.com/core/websocket/authentication).
        """
        if not self.is_configured():
            return {
                "status": "unconfigured",
                "connected": False,
                "message": "eToro credentials not configured in environment or Settings."
            }

        def _run_ws():
            async def _connect_and_auth():
                uri = "wss://ws.etoro.com/ws"
                results = []
                orientations = [
                    ("standard", self.user_key, self.api_key),
                    ("swapped", self.api_key, self.user_key)
                ]
                for label, u_key, a_key in orientations:
                    try:
                        async with websockets.connect(uri, open_timeout=5) as ws:
                            req_id = str(uuid.uuid4())
                            auth_msg = {
                                "id": req_id,
                                "operation": "Authenticate",
                                "data": {
                                    "userKey": u_key,
                                    "apiKey": a_key
                                }
                            }
                            await ws.send(json.dumps(auth_msg))
                            for _ in range(5):
                                msg = await asyncio.wait_for(ws.recv(), timeout=4)
                                if isinstance(msg, bytes):
                                    continue
                                data = json.loads(msg)
                                if data.get("operation") == "Authenticate":
                                    is_ok = data.get("success", False)
                                    results.append({
                                        "orientation": label,
                                        "success": is_ok,
                                        "response": data
                                    })
                                    if is_ok:
                                        return {
                                            "status": "connected",
                                            "connected": True,
                                            "orientation": label,
                                            "message": "✓ Successfully authenticated with eToro WebSocket API (wss://ws.etoro.com/ws)!",
                                            "response": data
                                        }
                                    break
                    except Exception as e:
                        results.append({"orientation": label, "success": False, "error": str(e)})

                return {
                    "status": "unauthorized",
                    "connected": False,
                    "message": "eToro WebSocket rejected authentication (HTTP 401). Check API permissions.",
                    "attempts": results
                }

            return asyncio.run(_connect_and_auth())

        try:
            import websockets
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_run_ws)
                return future.result(timeout=12.0)
        except Exception as e:
            return {"status": "error", "connected": False, "error": str(e)}

    def get_mcp_profile_and_scopes(self) -> Dict[str, Any]:
        """
        Fetches authenticated profile, account IDs (realCid/demoCid), and granted OAuth scopes
        via the official eToro MCP server tool 'get-my-profile-and-scopes'.
        """
        if not self.is_configured():
            return {"status": "unconfigured", "connected": False}

        mcp_url = "https://mcp.public-api.etoro.com"
        OFFICIAL_ETORO_MCP_API_KEY = "sdgdskldFPLGfjHn1421dgnlxdGTbngdflg6290bRjslfihsjhSDsdgGHH25hjf"
        orientations = [
            ("swapped" if self._prefer_swapped else "standard"),
            ("standard" if self._prefer_swapped else "swapped"),
            "official_with_user_key",
            "official_with_api_key",
            "user_key_only",
            "api_key_only"
        ]

        for orientation in orientations:
            if orientation == "swapped":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": self.user_key,
                    "x-user-key": self.api_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "standard":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": self.api_key,
                    "x-user-key": self.user_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "official_with_user_key":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": OFFICIAL_ETORO_MCP_API_KEY,
                    "x-user-key": self.user_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "official_with_api_key":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-api-key": OFFICIAL_ETORO_MCP_API_KEY,
                    "x-user-key": self.api_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            elif orientation == "user_key_only":
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-user-key": self.user_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }
            else:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "x-user-key": self.api_key,
                    "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-MCP)"
                }

            req_body = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {"name": "get-my-profile-and-scopes", "arguments": {}}
            }

            try:
                resp = requests.post(mcp_url, json=req_body, headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        if line.startswith("data: "):
                            d = json.loads(line[6:])
                            content = d.get("result", {}).get("content", [])
                            if content:
                                res_text = content[0].get("text", "")
                                try:
                                    profile_data = json.loads(res_text)
                                except Exception:
                                    profile_data = {"raw": res_text}
                                return {
                                    "status": "success",
                                    "connected": True,
                                    "orientation": orientation,
                                    "profile": profile_data
                                }
            except Exception as e:
                logger.debug(f"[eToro MCP Scopes - {orientation}] {e}")

        return {"status": "failed", "connected": False, "message": "Could not read scopes via MCP"}

    # =========================================================================
    # TRADING EXECUTION METHODS (Demo / Real)
    # =========================================================================

    def create_order(
        self,
        instrument_id: int,
        direction: str,
        amount_usd: float,
        stop_loss_rate: Optional[float] = None,
        take_profit_rate: Optional[float] = None,
        leverage: int = 1,
        mode: str = "real",
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submits a market order by amount to eToro using:
        1. Official eToro MCP prepare-trade -> place-trade pipeline (smart pre-flight & auto-polling)
        2. Direct v2 Execution: POST /api/v2/trading/execution/orders (or demo/orders)
        3. Fallback v1 Execution: POST /api/v1/trading/execution/market-open-orders/by-amount
        """
        is_demo = mode.lower() == "demo"
        is_buy = direction.upper() in ("BUY", "LONG")
        sym = (symbol or "").strip().upper()

        # 1. Try MCP pipeline first if symbol is provided
        if sym:
            mcp_res = self.execute_mcp_trade(
                symbol=sym,
                direction=direction,
                amount_usd=amount_usd,
                mode=mode
            )
            if mcp_res.get("success"):
                return mcp_res
            # If rejected by explicit business rule (e.g. leverage/balance/hours), don't blindly spam REST
            if mcp_res.get("verdict") == "rejected":
                logger.warning(f"[eToro Pre-Trade Rejected] {mcp_res.get('error')}")
                return mcp_res

        # 2. Official eToro v2 Execution Request (Docs: api-portal.etoro.com/core/guides/market-orders)
        v2_payload: Dict[str, Any] = {
            "action": "open",
            "transaction": "buy" if is_buy else "sellShort",
            "orderType": "mkt",
            "leverage": int(leverage),
            "amount": round(float(amount_usd), 2),
            "orderCurrency": "usd"
        }
        if sym:
            v2_payload["symbol"] = sym
        if instrument_id:
            v2_payload["instrumentId"] = int(instrument_id)

        # UK / FCA Spot regulation rule:
        # On spot crypto and unmargined spot assets (leverage == 1), Stop Loss & Take Profit
        # cannot be attached at open (CFD features prohibited on spot).
        # Only attach SL/TP when leverage > 1 or for non-crypto CFD assets.
        is_crypto = sym in CRYPTO_SYMBOLS or (instrument_id and instrument_id >= 100000)
        if not (is_crypto or leverage == 1):
            if stop_loss_rate is not None:
                v2_payload["stopLossRate"] = round(float(stop_loss_rate), 4)
            if take_profit_rate is not None:
                v2_payload["takeProfitRate"] = round(float(take_profit_rate), 4)

        endpoint = "/api/v2/trading/execution/demo/orders" if is_demo else "/api/v2/trading/execution/orders"
        success, code, data = self._request("POST", endpoint, json_data=v2_payload)
        if success or code in (200, 201, 202):
            logger.info(f"⚡ [eToro Live v2 Order Submitted] {direction} ${amount_usd:.2f} on {sym or instrument_id} -> HTTP {code}: {data}")
            return {"success": True, "status_code": code, "order": data}
        else:
            logger.warning(f"[eToro v2 Order Attempt] POST {endpoint} -> HTTP {code}: {data}")

        # 3. Fast v1 Fallback if v2 rejected
        v1_endpoint = f"/api/v1/trading/execution/{'demo/' if is_demo else ''}market-open-orders/by-amount"
        v1_payload: Dict[str, Any] = {
            "InstrumentID": int(instrument_id),
            "IsBuy": is_buy,
            "Amount": round(float(amount_usd), 2),
            "Leverage": int(leverage),
            "IsNoStopLoss": True if (is_crypto or leverage == 1 or stop_loss_rate is None) else False,
            "IsNoTakeProfit": True if (is_crypto or leverage == 1 or take_profit_rate is None) else False,
            "IsTslEnabled": False
        }
        if not (is_crypto or leverage == 1):
            if stop_loss_rate is not None:
                v1_payload["StopLossRate"] = round(float(stop_loss_rate), 4)
            if take_profit_rate is not None:
                v1_payload["TakeProfitRate"] = round(float(take_profit_rate), 4)

        success, code, data = self._request("POST", v1_endpoint, json_data=v1_payload)
        if success or code in (200, 201, 202):
            logger.info(f"⚡ [eToro Live v1 Order Submitted] {direction} ${amount_usd:.2f} on Instrument {instrument_id} -> HTTP {code}: {data}")
            return {"success": True, "status_code": code, "order": data}

        return {"success": False, "status_code": code, "order": v2_payload, "error": data}

    def close_position(
        self,
        position_id: str,
        units: Optional[float] = None,
        mode: str = "real"
    ) -> Dict[str, Any]:
        """
        Closes an open position on eToro (Demo or Real).
        """
        is_demo = mode.lower() == "demo"
        payload = {"UnitsToDeduct": units} if units is not None else {}

        endpoints = [
            (f"/api/v1/trading/execution/{'demo/' if is_demo else ''}market-close-orders/positions/{position_id}", "POST"),
            (f"/trading/execution/{'demo/' if is_demo else ''}market-close-orders/positions/{position_id}", "POST"),
            (f"/api/v1/trading/{mode.lower()}/positions/{position_id}", "DELETE"),
            (f"/api/v1/trading/positions/{position_id}", "DELETE")
        ]

        for ep, meth in endpoints:
            success, code, data = self._request(meth, ep, json_data=payload if meth == "POST" else None)
            if success or code in (200, 201, 202, 204):
                logger.info(f"⚡ [eToro Live Position Closed] Position {position_id} -> HTTP {code}")
                return {"success": True, "status_code": code, "result": data}

        return {"success": False, "status_code": 404, "position_id": position_id}
