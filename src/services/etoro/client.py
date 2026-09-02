"""
eToro Official REST API Connector Module.
Reference: https://api-portal.etoro.com/llms.txt and https://api-portal.etoro.com/mcp

Adheres to eToro API portal conventions:
- Injects x-api-key, x-user-key, and dynamic x-request-id (UUID v4) on every request.
- Manages HTTP 429 Rate Limits (60 req/min shared quota) using exponential backoff with jitter.
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
        self.base_url = (base_url or os.getenv("ETORO_BASE_URL", "https://api.etoro.com")).rstrip("/")
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec

    def is_configured(self) -> bool:
        """Checks if both public API key and private User key are present."""
        return bool(self.api_key and len(self.api_key) > 5 and self.user_key and len(self.user_key) > 5)

    def _build_headers(self) -> Dict[str, str]:
        """
        Builds standard required eToro HTTP headers, injecting
        x-api-key, x-user-key, and a unique UUID v4 x-request-id.
        """
        return {
            "x-api-key": self.api_key,
            "x-user-key": self.user_key,
            "x-request-id": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Autonomous-Trading-Cockpit/2.0 (eToro-Client)"
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0
    ) -> Tuple[bool, int, Dict[str, Any]]:
        """
        Executes HTTP request to eToro API with automatic exponential backoff for HTTP 429 rate limits.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(1, self.max_retries + 1):
            headers = self._build_headers()
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
                        f"Backing off for {sleep_time:.2f}s... (x-request-id: {req_id})"
                    )
                    time.sleep(sleep_time)
                    continue

                # Parse JSON body
                try:
                    res_json = response.json()
                except Exception:
                    res_json = {"raw_text": response.text}

                if 200 <= response.status_code < 300:
                    return True, response.status_code, res_json
                else:
                    logger.error(
                        f"[eToro API Error] {method} {endpoint} -> HTTP {response.status_code}: {res_json} (x-request-id: {req_id})"
                    )
                    return False, response.status_code, res_json

            except requests.exceptions.RequestException as e:
                logger.error(f"[eToro Network Exception] Attempt {attempt}/{self.max_retries}: {e}")
                if attempt == self.max_retries:
                    return False, 500, {"error": str(e), "message": "Network connectivity failure to eToro API"}
                time.sleep(self.base_backoff_sec * attempt)

        return False, 429, {"error": "Rate limit exceeded after maximum retries"}

    # =========================================================================
    # VERIFICATION & READ-ONLY METHODS (Zero Risk)
    # =========================================================================

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests and verifies connection to the eToro API without placing any trades.
        Validates API keys and queries the identity/profile and system status.
        """
        if not self.is_configured():
            return {
                "status": "unconfigured",
                "connected": False,
                "message": "eToro API credentials missing. Please configure ETORO_API_KEY and ETORO_USER_KEY in .env or Settings.",
                "base_url": self.base_url,
                "has_api_key": bool(self.api_key),
                "has_user_key": bool(self.user_key)
            }

        # 1. Ping identity profile endpoint
        success, status_code, data = self._request("GET", "/api/v1/identity/profile")
        
        if success:
            return {
                "status": "connected",
                "connected": True,
                "message": "✓ Successfully authenticated with eToro API!",
                "status_code": status_code,
                "base_url": self.base_url,
                "profile": data,
                "timestamp": time.time()
            }
        else:
            # Check market data fallback if identity requires OAuth scope
            m_success, m_code, m_data = self._request("GET", "/api/v1/market-data/instruments?search=AAPL")
            if m_success:
                return {
                    "status": "connected_market_data",
                    "connected": True,
                    "message": "✓ Authenticated with eToro Market Data API!",
                    "status_code": m_code,
                    "base_url": self.base_url,
                    "details": m_data,
                    "timestamp": time.time()
                }

            return {
                "status": "authentication_failed",
                "connected": False,
                "message": f"Authentication rejected by eToro API (HTTP {status_code}). Please verify your ETORO_API_KEY and ETORO_USER_KEY.",
                "status_code": status_code,
                "error_details": data,
                "base_url": self.base_url
            }

    def get_account_balances(self) -> Dict[str, Any]:
        """Fetches cash balance, total invested, and equity from eToro."""
        success, code, data = self._request("GET", "/api/v1/balances/accounts")
        return {"success": success, "status_code": code, "data": data}

    def get_portfolio(self, mode: str = "demo") -> Dict[str, Any]:
        """Fetches active open positions and portfolio details (demo or real)."""
        ep = f"/api/v1/trading/{mode.lower()}/portfolio"
        success, code, data = self._request("GET", ep)
        return {"success": success, "status_code": code, "data": data}

    def search_instruments(self, query: str) -> List[Dict[str, Any]]:
        """Searches for tradable instruments by ticker symbol or company name."""
        success, _, data = self._request("GET", "/api/v1/market-data/instruments", params={"search": query})
        if success and isinstance(data, list):
            return data
        elif success and isinstance(data, dict):
            return data.get("items", [data])
        return []

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
        mode: str = "demo"
    ) -> Dict[str, Any]:
        """
        Submits a market order to eToro (Demo or Real environment).
        """
        payload = {
            "InstrumentID": instrument_id,
            "IsBuy": direction.upper() in ("BUY", "LONG"),
            "Amount": amount_usd,
            "Leverage": leverage
        }
        if stop_loss_rate is not None:
            payload["StopLossRate"] = stop_loss_rate
        if take_profit_rate is not None:
            payload["TakeProfitRate"] = take_profit_rate

        ep = f"/api/v1/trading/{mode.lower()}/orders"
        success, code, data = self._request("POST", ep, json_data=payload)
        return {"success": success, "status_code": code, "order": data}

    def close_position(
        self,
        position_id: str,
        units: Optional[float] = None,
        mode: str = "demo"
    ) -> Dict[str, Any]:
        """
        Closes an open position on eToro (Demo or Real).
        """
        ep = f"/api/v1/trading/{mode.lower()}/positions/{position_id}"
        payload = {"Units": units} if units is not None else None
        success, code, data = self._request("DELETE", ep, json_data=payload)
        return {"success": success, "status_code": code, "result": data}
