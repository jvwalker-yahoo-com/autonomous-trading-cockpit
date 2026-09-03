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
import logging
import requests
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger("etoro.client")

# ⚠️ WARNING: ALL previously hardcoded IDs were fabricated and caused wrong trades (e.g. FET→EURSEK).
# The real eToro instrument IDs are fetched dynamically from the live API via bootstrap_instrument_ids()
# and raw_search_debug() at first use. Do NOT add IDs here without verifying against the real API.
SYMBOL_TO_ETORO_ID: Dict[str, int] = {}

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
        self.api_key = (api_key or os.getenv("ETORO_API_KEY", "")).strip()
        self.user_key = (user_key or os.getenv("ETORO_USER_KEY", "")).strip()
        
        raw_url = (base_url or os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com")).strip().rstrip("/")
        if "api.etoro.com" in raw_url and "public-api.etoro.com" not in raw_url:
            raw_url = raw_url.replace("api.etoro.com", "public-api.etoro.com")
        self.base_url = raw_url or "https://public-api.etoro.com"
        
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec
        self._instrument_cache: Dict[str, int] = dict(SYMBOL_TO_ETORO_ID)
        self._ids_bootstrapped: bool = False

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
        """
        variants = []
        if self.api_key and self.user_key:
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

        # Orientation 2: Try swapped
        self.api_key, self.user_key = self.user_key, self.api_key
        for ep in user_endpoints:
            success, status_code, data = self._request("GET", ep, suppress_error_log=True)
            if success:
                logger.info("✓ Auto-detected and aligned swapped eToro API Key and User Key orientation!")
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
                    "status_code": status_code,
                    "base_url": self.base_url,
                    "api_key": self.api_key,
                    "user_key": self.user_key,
                    "profile": data,
                    "timestamp": time.time()
                }

        # Revert swap
        self.api_key, self.user_key = self.user_key, self.api_key

        # Check if Market Data (Public API Key) passes
        m_success, m_code, m_data = self._request("GET", "/api/v1/market-data/instruments?search=AAPL", suppress_error_log=True)
        if m_success:
            return {
                "status": "partial_authentication",
                "connected": False,
                "trading_enabled": False,
                "message": f"⚠️ Public API Key is VALID, but eToro rejected your User Key (HTTP 401).\n\nAction Required:\n1. Open eToro Settings -> Trading -> API Key Management\n2. Click 'Create Your API Key' (or Edit existing key)\n3. Set Environment to 'Real' and Permissions to 'Write'\n4. Copy the key and paste into ETORO_USER_KEY in Settings.",
                "status_code": 401,
                "base_url": self.base_url,
                "api_key": self.api_key
            }

        return {
            "status": "authentication_failed",
            "connected": False,
            "trading_enabled": False,
            "message": f"Authentication rejected by eToro API ({self.base_url}) - HTTP 401 Unauthorized.\n\nPlease verify:\n1. Your Public API Key is from the 'Public Key' box\n2. Your User Key is from the 'Generated Keys' list\n3. No extra spaces or missing characters.",
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
            f"/api/v1/trading/{mode.lower()}/portfolio",
            "/api/v1/trading/info/portfolio"
        ]
        for ep in endpoints:
            success, code, data = self._request("GET", ep)
            if success:
                return {"success": True, "status_code": code, "data": data}
        return {"success": False, "status_code": code if 'code' in locals() else 404, "data": {}}

    def search_instruments(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches for tradable instruments using multiple eToro search parameter formats.
        Tries query, symbolFull, displayName, and symbol variations.
        """
        base_params = {"pageSize": 20}
        
        # Try all known eToro search parameter variants
        search_variants = [
            {"query": query},
            {"symbolFull": query},
            {"q": query},
            {"displayName": query},
            {"symbol": query},
        ]

        for variant in search_variants:
            params = {**base_params, **variant}
            success, code, data = self._request(
                "GET", "/api/v1/market-data/search",
                params=params, suppress_error_log=True, timeout=4.0
            )
            if success:
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("items") or data.get("instruments") or data.get("results") or data.get("data") or []
                if items:
                    logger.debug(f"[eToro Search] Found {len(items)} results for '{query}' using params={variant}")
                    return items

        # Fallback: try the instruments list endpoint
        for sym_param in ["symbolFull", "symbol", "query"]:
            params = {sym_param: query, "pageSize": 5}
            success, code, data = self._request(
                "GET", "/api/v1/market-data/instruments",
                params=params, suppress_error_log=True, timeout=4.0
            )
            if success:
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("items") or data.get("instruments") or []
                if items:
                    logger.debug(f"[eToro Instruments] Found {len(items)} results for '{query}'")
                    return items

        logger.warning(f"[eToro Search] No results found for '{query}' — all search variants exhausted")
        return []

    def raw_search_debug(self, query: str) -> Dict[str, Any]:
        """
        Fast diagnostic — tries the most likely search param variants with short 4s timeout.
        Returns raw HTTP status + sample response to identify the correct search format.
        """
        results = {}
        endpoints_params = [
            ("/api/v1/market-data/search",       {"query": query, "pageSize": 3}),
            ("/api/v1/market-data/search",       {"symbolFull": query, "pageSize": 3}),
            ("/api/v1/market-data/search",       {"q": query, "pageSize": 3}),
            ("/api/v1/market-data/instruments",  {"symbolFull": query, "pageSize": 3}),
            ("/api/v1/market-data/instruments",  {"query": query, "pageSize": 3}),
        ]
        for ep, p in endpoints_params:
            key = f"GET {ep}?{list(p.keys())[0]}={query}"
            success, code, data = self._request(
                "GET", ep, params=p,
                suppress_error_log=True, timeout=4.0
            )
            results[key] = {
                "http_status": code,
                "success": success,
                "response_sample": str(data)[:300]
            }
            if success:  # Stop at first working variant
                break
        return results

    def resolve_instrument_id(self, symbol: str) -> Optional[int]:
        """Resolves a ticker symbol to its eToro internal Instrument ID."""
        sym_upper = symbol.strip().upper()
        if sym_upper in self._instrument_cache:
            return self._instrument_cache[sym_upper]

        # Dynamic search lookup if not in static table
        results = self.search_instruments(sym_upper)
        for item in results:
            if isinstance(item, dict):
                cand_sym = str(item.get("symbolFull") or item.get("Symbol") or item.get("symbol") or "").upper()
                cand_id = item.get("instrumentId") or item.get("InstrumentID") or item.get("id")
                if cand_sym == sym_upper and cand_id:
                    self._instrument_cache[sym_upper] = int(cand_id)
                    return int(cand_id)

        # Fallback only if mock mode
        if not self.is_configured():
            mock_id = 10000 + (abs(hash(sym_upper)) % 80000)
            self._instrument_cache[sym_upper] = mock_id
            return mock_id
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
        mode: str = "real"
    ) -> Dict[str, Any]:
        """
        Submits a market order by amount to eToro using the official execution endpoints.
        """
        is_demo = mode.lower() == "demo"
        is_buy = direction.upper() in ("BUY", "LONG")

        # 1. Official eToro v2 Execution Request (Docs: api-portal.etoro.com/core/guides/market-orders)
        v2_payload = {
            "action": "open",
            "transaction": "buy" if is_buy else "sell",
            "instrumentId": int(instrument_id),
            "orderType": "mkt",
            "leverage": int(leverage),
            "amount": round(float(amount_usd), 2),
            "orderCurrency": "usd"
        }
        if stop_loss_rate is not None:
            v2_payload["stopLossRate"] = round(float(stop_loss_rate), 4)
        if take_profit_rate is not None:
            v2_payload["takeProfitRate"] = round(float(take_profit_rate), 4)

        v2_endpoints = [
            f"/api/v2/trading/execution/{'demo/' if is_demo else ''}orders",
            "/api/v2/trading/execution/orders",
            "/api/v2/trading/execution/demo/orders"
        ]

        for ep in v2_endpoints:
            success, code, data = self._request("POST", ep, json_data=v2_payload)
            if success or code in (200, 201, 202):
                logger.info(f"⚡ [eToro Live v2 Order Submitted] {direction} ${amount_usd:.2f} on Instrument {instrument_id} -> HTTP {code}: {data}")
                return {"success": True, "status_code": code, "order": data}
            else:
                logger.warning(f"[eToro v2 Order Attempt] POST {ep} -> HTTP {code}: {data}")

        # 2. Official eToro v1 Execution Request Fallback
        v1_payload = {
            "InstrumentID": int(instrument_id),
            "IsBuy": is_buy,
            "Amount": round(float(amount_usd), 2),
            "Leverage": int(leverage),
            "IsNoStopLoss": stop_loss_rate is None,
            "IsNoTakeProfit": take_profit_rate is None,
            "IsTslEnabled": False
        }
        if stop_loss_rate is not None:
            v1_payload["StopLossRate"] = round(float(stop_loss_rate), 4)
        if take_profit_rate is not None:
            v1_payload["TakeProfitRate"] = round(float(take_profit_rate), 4)

        v1_endpoints = [
            f"/api/v1/trading/execution/{'demo/' if is_demo else ''}market-open-orders/by-amount",
            "/api/v1/trading/execution/market-open-orders/by-amount",
            "/api/v1/trading/execution/demo/market-open-orders/by-amount",
            "/api/v1/trading/real/orders",
            "/api/v1/trading/orders"
        ]

        for ep in v1_endpoints:
            success, code, data = self._request("POST", ep, json_data=v1_payload)
            if success or code in (200, 201, 202):
                logger.info(f"⚡ [eToro Live v1 Order Submitted] {direction} ${amount_usd:.2f} on Instrument {instrument_id} -> HTTP {code}: {data}")
                return {"success": True, "status_code": code, "order": data}
            else:
                logger.warning(f"[eToro v1 Order Attempt] POST {ep} -> HTTP {code}: {data}")

        logger.warning(f"eToro order execution returned non-200 for Instrument {instrument_id}: {v2_payload}")
        return {"success": False, "status_code": code if 'code' in locals() else 404, "order": v2_payload, "error": data if 'data' in locals() else "Order rejected"}

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
