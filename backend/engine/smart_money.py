"""
SmartMoneyEngine — Congressional Stock Disclosures & Institutional Intelligence.

Integrates:
  1. CongressInvests API (Real-time STOCK Act disclosure tracking across US House & Senate)
     Source: https://congressinfor-production.up.railway.app
  2. Equibles MCP Server (JSON-RPC 2.0 / SSE with 117 financial intelligence tools)
     Source: https://mcp.equibles.com/mcp?api_key=...

Provides:
  - Market-wide Congressional net buy/sell flow analysis
  - Per-symbol Congressional Conviction Score (-1.0 to +1.0)
  - Short squeeze scores & Corporate Insider accumulation ranking
  - Cross-matched high-conviction trade candidate discovery
"""
import time
import math
import re
import json
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("auton-cockpit.smart_money")

CONGRESS_AMOUNT_WEIGHTS = {
    "$1,001 - $15,000": 1.0,
    "$15,001 - $50,000": 3.0,
    "$50,001 - $100,000": 6.0,
    "$100,001 - $250,000": 12.0,
    "$250,001 - $500,000": 25.0,
    "$500,001 - $1,000,000": 50.0,
    "$1,000,001 - $5,000,000": 100.0,
    "Over $1,000,000": 100.0,
    "Over $5,000,000": 250.0,
    "Over $50,000,000": 1000.0,
}

class SmartMoneyEngine:
    def __init__(
        self,
        equibles_api_key: str = "eq_1a4793cb907bc87e163c0b457166914a95c86e8e",
        congress_invests_url: str = "https://congressinfor-production.up.railway.app",
        tavily_api_key: str = "",
        serpapi_api_key: str = "",
        anspire_api_key: str = ""
    ):
        self.equibles_api_key = equibles_api_key.strip()
        self.congress_invests_url = congress_invests_url.rstrip("/")
        self.equibles_mcp_url = f"https://mcp.equibles.com/mcp?api_key={self.equibles_api_key}"
        self.tavily_api_key = tavily_api_key.strip()
        self.serpapi_api_key = serpapi_api_key.strip()
        self.anspire_api_key = anspire_api_key.strip()
        
        self._lock = threading.Lock()
        
        # In-memory caches
        self._recent_congress_trades: List[Dict[str, Any]] = []
        self._symbol_congress_scores: Dict[str, float] = {}
        self._symbol_congress_trades: Dict[str, List[Dict[str, Any]]] = {}
        self._congress_news_articles: List[Dict[str, Any]] = []
        self._equibles_market_buying: str = ""
        self._equibles_short_squeeze: str = ""
        self._equibles_insider_sentiment: str = ""
        self._trade_candidates: List[Dict[str, Any]] = []
        
        self._last_refresh: float = 0.0
        self._cache_ttl: float = 900.0  # 15 minutes cache

    def set_equibles_key(self, key: str):
        with self._lock:
            self.equibles_api_key = key.strip()
            self.equibles_mcp_url = f"https://mcp.equibles.com/mcp?api_key={self.equibles_api_key}"

    def set_feed_keys(self, tavily_key: str = "", serpapi_key: str = "", anspire_key: str = ""):
        with self._lock:
            if tavily_key:
                self.tavily_api_key = tavily_key.strip()
            if serpapi_key:
                self.serpapi_api_key = serpapi_key.strip()
            if anspire_key:
                self.anspire_api_key = anspire_key.strip()


    # ── CongressInvests Client ──────────────────────────────────────────────

    def fetch_congress_invests_recent(self, limit: int = 50, days: int = 30) -> List[Dict[str, Any]]:
        """Fetches recent congressional trades from CongressInvests API."""
        import requests
        url = f"{self.congress_invests_url}/trades/recent?limit={limit}&days={days}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("trades", [])
        except Exception as e:
            logger.warning(f"CongressInvests recent trades fetch error: {e}")
        return []

    def fetch_congress_invests_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        """Fetches congressional trading history for a specific ticker."""
        import requests
        url = f"{self.congress_invests_url}/trades/{ticker.upper().strip()}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("trades", [])
        except Exception as e:
            logger.debug(f"CongressInvests ticker {ticker} fetch error: {e}")
        return []

    # ── Equibles MCP JSON-RPC Client ────────────────────────────────────────

    def call_equibles_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Invokes a tool on Equibles MCP server via JSON-RPC 2.0 / SSE."""
        import requests
        headers = {"Content-Type": "application/json"}
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        try:
            resp = requests.post(self.equibles_mcp_url, json=payload, headers=headers, timeout=12)
            if resp.status_code == 200:
                for line in resp.text.strip().split("\n"):
                    if line.startswith("data:"):
                        res_data = json.loads(line[5:].strip())
                        content = res_data.get("result", {}).get("content", [])
                        if content:
                            return content[0].get("text", "")
        except Exception as e:
            logger.warning(f"Equibles MCP call '{tool_name}' error: {e}")
        return ""

    # ── Tavily & SerpApi Congressional Intelligence Search ──────────────────

    def fetch_congress_tavily(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Queries Tavily AI Search for breaking US Congress stock trades and STOCK Act filings."""
        if not self.tavily_api_key or len(self.tavily_api_key) < 5:
            return []
        import requests
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_api_key,
                    "query": "US Congress member stock trades recent purchases sales STOCK Act 2026",
                    "search_depth": "basic",
                    "max_results": limit
                },
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
        except Exception as e:
            logger.debug(f"Tavily congress search notice: {e}")
        return []

    def fetch_congress_serpapi(self) -> List[Dict[str, Any]]:
        """Queries SerpApi for breaking news and reports on congressional stock trading."""
        if not self.serpapi_api_key or len(self.serpapi_api_key) < 5:
            return []
        import requests
        try:
            url = f"https://serpapi.com/search.json?q=congress+stock+trades+disclosures&api_key={self.serpapi_key}"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("organic_results", [])[:5]
        except Exception as e:
            logger.debug(f"SerpApi congress search notice: {e}")
        return []

    # ── Smart Money Refresh & Trade Candidate Identification ────────────────

    def refresh_all(self, watchlist: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Refreshes all congressional & institutional data across CongressInvests, Tavily AI,
        SerpApi, and Equibles. Computes per-symbol scores and surfaces trade opportunities.
        """
        now = time.time()
        logger.info("🏛️ [SMART MONEY] Refreshing Congressional & Institutional Intelligence...")

        # 1. Fetch CongressInvests recent trades
        recent_trades = self.fetch_congress_invests_recent(limit=60, days=30)
        
        # 2. Query Tavily and SerpApi Congressional Intelligence
        tavily_articles = self.fetch_congress_tavily(limit=5)
        serp_articles = self.fetch_congress_serpapi()
        congress_articles = []
        for art in tavily_articles:
            congress_articles.append({
                "title": art.get("title", ""),
                "url": art.get("url", ""),
                "snippet": art.get("content", "")[:250],
                "source": "Tavily AI"
            })
        for art in serp_articles:
            congress_articles.append({
                "title": art.get("title", ""),
                "url": art.get("link", ""),
                "snippet": art.get("snippet", "")[:250],
                "source": "SerpApi"
            })

        # 3. Query Equibles Market-Wide Congressional Activity & Short Squeeze
        eq_buying = self.call_equibles_tool("GetMarketWideCongressionalActivity", {"direction": "buys", "limit": 15})
        eq_squeeze = self.call_equibles_tool("GetShortSqueezeScores", {"limit": 10})
        eq_insiders = self.call_equibles_tool("GetInsiderSentimentScores", {"limit": 10})

        # 4. Calculate per-symbol Congressional net conviction scores
        new_scores: Dict[str, float] = {}
        symbol_trades_map: Dict[str, List[Dict[str, Any]]] = {}
        today = datetime.now(timezone.utc).date()

        for t in recent_trades:
            ticker = (t.get("ticker") or "").upper().strip()
            if not ticker or ticker in ("N/A", "NONE"):
                continue

            symbol_trades_map.setdefault(ticker, []).append(t)
            
            # Weight based on disclosed amount
            amt_str = t.get("amount", "")
            base_weight = CONGRESS_AMOUNT_WEIGHTS.get(amt_str, 2.0)
            
            # Time decay (fresher disclosure = higher weight)
            disclosed_str = t.get("disclosed", "") or t.get("tx_date", "")
            recency_mult = 1.0
            if disclosed_str:
                try:
                    disc_date = datetime.strptime(disclosed_str[:10], "%Y-%m-%d").date()
                    days_ago = (today - disc_date).days
                    if days_ago <= 7:
                        recency_mult = 1.5
                    elif days_ago <= 21:
                        recency_mult = 1.0
                    else:
                        recency_mult = 0.6
                except Exception:
                    pass

            trade_type = (t.get("trade_type") or "").lower()
            direction = 1.0 if "buy" in trade_type or "purchase" in trade_type else (-1.0 if "sell" in trade_type or "sale" in trade_type else 0.0)
            
            new_scores[ticker] = new_scores.get(ticker, 0.0) + (direction * base_weight * recency_mult)

        # Parse Equibles buying table to extract additional tickers and net flow
        # Markdown table parsing: | 1 | MSFT | 2 | 3 | ... | +$24.5K |
        for line in eq_buying.split("\n"):
            if "|" in line and not line.startswith("|-") and not line.startswith("| #"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 9:
                    sym = parts[2].upper().strip()
                    net_str = parts[8].replace("$", "").replace(",", "").replace("+", "").strip()
                    if sym and sym.isalpha() and len(sym) <= 5:
                        multiplier = 1000.0 if "K" in net_str else (1000000.0 if "M" in net_str else 1.0)
                        try:
                            val_num = float(re.sub(r"[^\d.-]", "", net_str)) * multiplier
                            eq_score = max(-20.0, min(20.0, val_num / 25000.0))
                            new_scores[sym] = new_scores.get(sym, 0.0) + eq_score
                        except Exception:
                            new_scores[sym] = new_scores.get(sym, 0.0) + 5.0

        # Corroborate with Tavily search articles
        for art in congress_articles:
            text = (art.get("title", "") + " " + art.get("snippet", "")).upper()
            for sym in list(new_scores.keys()):
                if f" {sym} " in text or f"${sym}" in text:
                    new_scores[sym] = new_scores.get(sym, 0.0) + 3.0

        # Normalize all scores to [-1.0, +1.0] using hyperbolic tangent scaling
        normalized_scores: Dict[str, float] = {}
        for sym, raw in new_scores.items():
            norm = math.tanh(raw / 12.0)
            normalized_scores[sym] = round(max(-1.0, min(1.0, norm)), 3)

        # 5. Identify Potential Trade Setups (Cross-matching Congressional Buys with Watchlist/Anchors)
        candidates: List[Dict[str, Any]] = []
        for sym, score in sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True):
            if score >= 0.08:
                trades_for_sym = symbol_trades_map.get(sym, [])
                top_members = list(dict.fromkeys([t.get("member") for t in trades_for_sym if t.get("member")]))
                buyers_desc = top_members[:3] if top_members else ["Market-Wide Net Flow"]
                source_label = "CongressInvests"
                if self.tavily_api_key:
                    source_label += " + Tavily AI"
                if self.equibles_api_key:
                    source_label += " + Equibles MCP"
                
                candidates.append({
                    "symbol": sym,
                    "signal": "CONGRESS_BUY",
                    "conviction_score": score,
                    "buyers": buyers_desc,
                    "total_trades": len(trades_for_sym),
                    "latest_filing": trades_for_sym[0].get("disclosed") if trades_for_sym else "Recent Disclosure",
                    "recent_filings": trades_for_sym[:3],
                    "source": source_label
                })

        # Commit atomically
        with self._lock:
            self._recent_congress_trades = recent_trades
            self._symbol_congress_scores = normalized_scores
            self._symbol_congress_trades = symbol_trades_map
            self._congress_news_articles = congress_articles
            self._equibles_market_buying = eq_buying
            self._equibles_short_squeeze = eq_squeeze
            self._equibles_insider_sentiment = eq_insiders
            self._trade_candidates = candidates
            self._last_refresh = now

        top_buys = [f"{c['symbol']}:+{c['conviction_score']:.2f}" for c in candidates[:6]]
        logger.info(f"🏛️ [SMART MONEY] Refresh complete! Top Congressional Buys: {top_buys}")

        return {
            "total_trades_analyzed": len(recent_trades),
            "candidates_count": len(candidates),
            "top_candidates": candidates[:10],
            "articles_count": len(congress_articles)
        }


    # ── Public Accessors ────────────────────────────────────────────────────

    def get_congress_conviction(self, symbol: str) -> float:
        """Returns Congressional conviction score [-1.0 to +1.0] for a symbol."""
        with self._lock:
            return self._symbol_congress_scores.get(symbol.upper().strip(), 0.0)

    def get_symbol_trades(self, symbol: str) -> List[Dict[str, Any]]:
        """Returns recorded congressional trades for a specific symbol."""
        with self._lock:
            return list(self._symbol_congress_trades.get(symbol.upper().strip(), []))

    def get_recent_trades(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Returns latest market-wide congressional disclosures."""
        with self._lock:
            return list(self._recent_congress_trades[:limit])

    def get_trade_candidates(self) -> List[Dict[str, Any]]:
        """Returns identified potential trades based on Smart Money accumulation."""
        with self._lock:
            return list(self._trade_candidates)

    def get_all_scores(self) -> Dict[str, float]:
        """Returns all current Congressional conviction scores."""
        with self._lock:
            return dict(self._symbol_congress_scores)

    def get_equibles_reports(self) -> Dict[str, str]:
        """Returns Equibles market-wide congressional, short squeeze, and insider reports."""
        with self._lock:
            return {
                "market_wide_buying": self._equibles_market_buying,
                "short_squeeze_scores": self._equibles_short_squeeze,
                "insider_sentiment": self._equibles_insider_sentiment
            }
