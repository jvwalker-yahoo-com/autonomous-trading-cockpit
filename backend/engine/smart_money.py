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
        anspire_api_key: str = "",
        finnhub_api_key: str = "",
        quiver_api_key: str = ""
    ):
        self.equibles_api_key = equibles_api_key.strip()
        self.congress_invests_url = congress_invests_url.rstrip("/")
        self.equibles_mcp_url = f"https://mcp.equibles.com/mcp?api_key={self.equibles_api_key}"
        self.tavily_api_key = tavily_api_key.strip()
        self.serpapi_api_key = serpapi_api_key.strip()
        self.anspire_api_key = anspire_api_key.strip()
        self.finnhub_api_key = finnhub_api_key.strip()
        self.quiver_api_key = quiver_api_key.strip()
        
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
        
        # OpenInsider & Institutional 13F caches (3-Way Transparency Flow)
        self._openinsider_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._institutional_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._transparency_feed_cache: Dict[str, Dict[str, Any]] = {}
        
        self._last_refresh: float = 0.0
        self._cache_ttl: float = 900.0  # 15 minutes cache

    def set_equibles_key(self, key: str):
        with self._lock:
            self.equibles_api_key = key.strip()
            self.equibles_mcp_url = f"https://mcp.equibles.com/mcp?api_key={self.equibles_api_key}"

    def set_feed_keys(
        self,
        tavily_key: str = "",
        serpapi_key: str = "",
        anspire_key: str = "",
        finnhub_key: str = "",
        quiver_key: str = ""
    ):
        with self._lock:
            if tavily_key:
                self.tavily_api_key = tavily_key.strip()
            if serpapi_key:
                self.serpapi_api_key = serpapi_key.strip()
            if anspire_key:
                self.anspire_api_key = anspire_key.strip()
            if finnhub_key:
                self.finnhub_api_key = finnhub_key.strip()
            if quiver_key:
                self.quiver_api_key = quiver_key.strip()


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

    def get_flow_conviction(self, symbol: str) -> float:
        """Returns unified 3-way flow transparency conviction score [-1.0 to +1.0] for a symbol."""
        sym = symbol.upper().strip()
        with self._lock:
            cached = self._transparency_feed_cache.get(sym)
            if cached and "flow_conviction" in cached:
                return float(cached.get("flow_conviction", 0.0))
            return self._symbol_congress_scores.get(sym, 0.0)

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

    # ── 3-Way Transparency Flow Stack: OpenInsider + QuiverQuant + Finnhub 13F ──

    def fetch_openinsider_trades(self, symbol: Optional[str] = None, limit: int = 35) -> List[Dict[str, Any]]:
        """
        Scrapes real-time Form 4 insider trades (officers, directors, 10% owners) from OpenInsider.
        Free, open-source transparency feed, zero API key required.
        """
        import requests
        sym_param = symbol.upper().strip() if symbol else ""
        url = f"http://openinsider.com/screener?s={sym_param}&cnt={limit}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        trades: List[Dict[str, Any]] = []
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', resp.text, re.DOTALL)
                for row in rows:
                    tds = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.DOTALL)
                    if len(tds) >= 12:
                        tick_m = re.search(r'>([A-Z0-9]{1,6})</a>', tds[3]) or re.search(r'href="/([A-Z0-9]{1,6})"', tds[3])
                        ticker = tick_m.group(1) if tick_m else (sym_param or "STOCK")
                        filing_date = re.sub(r'<[^>]+>', '', tds[1]).strip()
                        trade_date = re.sub(r'<[^>]+>', '', tds[2]).strip()
                        if sym_param:
                            name = re.sub(r'<[^>]+>', '', tds[4]).strip()
                            title = re.sub(r'<[^>]+>', '', tds[5]).strip()
                            trade_type = re.sub(r'<[^>]+>', '', tds[6]).strip()
                            price_str = re.sub(r'<[^>]+>', '', tds[7]).strip()
                            qty_str = re.sub(r'<[^>]+>', '', tds[8]).strip()
                            val_str = re.sub(r'<[^>]+>', '', tds[11]).strip()
                        else:
                            name = re.sub(r'<[^>]+>', '', tds[5]).strip()
                            title = re.sub(r'<[^>]+>', '', tds[6]).strip()
                            trade_type = re.sub(r'<[^>]+>', '', tds[7]).strip()
                            price_str = re.sub(r'<[^>]+>', '', tds[8]).strip()
                            qty_str = re.sub(r'<[^>]+>', '', tds[9]).strip()
                            val_str = re.sub(r'<[^>]+>', '', tds[12] if len(tds) > 12 else tds[11]).strip()
                        
                        is_purchase = trade_type.upper().startswith("P") or "PURCHASE" in trade_type.upper()
                        is_sale = trade_type.upper().startswith("S") or "SALE" in trade_type.upper()
                        
                        try:
                            price_num = float(re.sub(r"[^\d.]", "", price_str)) if price_str else 0.0
                        except Exception:
                            price_num = 0.0
                        try:
                            qty_num = int(re.sub(r"[^\d-]", "", qty_str)) if qty_str else 0
                        except Exception:
                            qty_num = 0
                        try:
                            val_num = float(re.sub(r"[^\d.-]", "", val_str)) if val_str else 0.0
                        except Exception:
                            val_num = 0.0
                            
                        trades.append({
                            "ticker": ticker,
                            "name": name,
                            "title": title,
                            "trade_type": trade_type,
                            "is_purchase": is_purchase,
                            "is_sale": is_sale,
                            "price": price_num,
                            "qty": qty_num,
                            "value_usd": val_num,
                            "filing_date": filing_date,
                            "trade_date": trade_date,
                            "source": "OpenInsider Form 4"
                        })
                with self._lock:
                    if sym_param:
                        self._openinsider_cache[sym_param] = trades
        except Exception as e:
            logger.debug(f"OpenInsider scrape error ({sym_param}): {e}")
        return trades

    def fetch_finnhub_insiders(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetches official Form 4 insider transactions from Finnhub."""
        if not self.finnhub_api_key or len(self.finnhub_api_key) < 5:
            return []
        import requests
        sym = symbol.upper().strip()
        url = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={sym}&token={self.finnhub_api_key}"
        try:
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                formatted = []
                for item in data[:30]:
                    t_code = str(item.get("transactionCode", "")).upper()
                    is_p = (t_code == "P")
                    is_s = (t_code == "S")
                    change = item.get("change", 0)
                    price = float(item.get("transactionPrice", 0.0) or 0.0)
                    val = round(abs(change) * price, 2)
                    formatted.append({
                        "ticker": sym,
                        "name": item.get("name", "Insider"),
                        "title": "Officer/Director",
                        "trade_type": "Purchase (P)" if is_p else ("Sale (S)" if is_s else f"Form 4 ({t_code})"),
                        "is_purchase": is_p or change > 0,
                        "is_sale": is_s or change < 0,
                        "price": price,
                        "qty": change,
                        "value_usd": val if not is_s else -val,
                        "filing_date": item.get("filingDate", ""),
                        "trade_date": item.get("transactionDate", ""),
                        "source": "Finnhub SEC Form 4"
                    })
                return formatted
        except Exception as e:
            logger.debug(f"Finnhub insider fetch error {sym}: {e}")
        return []

    def fetch_quiver_congress_trades(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches Congressional trading disclosures from QuiverQuant's Congress Trading API.
        Cascades to CongressInvests and Tavily AI search if needed.
        """
        import requests
        sym = symbol.upper().strip() if symbol else ""
        headers = {"User-Agent": "Mozilla/5.0"}
        if self.quiver_api_key:
            headers["Authorization"] = f"Token {self.quiver_api_key}"
            
        trades = []
        try:
            url = "https://api.quiverquant.com/beta/live/congresstrading"
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                raw_list = resp.json()
                if isinstance(raw_list, list):
                    for item in raw_list:
                        item_ticker = (item.get("Ticker") or "").upper().strip()
                        if sym and item_ticker != sym:
                            continue
                        tx_type = item.get("Transaction", "Purchase")
                        trades.append({
                            "representative": item.get("Representative", "Congress Member"),
                            "chamber": item.get("House", "Congress"),
                            "party": item.get("Party", ""),
                            "ticker": item_ticker,
                            "transaction_type": tx_type,
                            "amount_range": item.get("Range", "$15,001 - $50,000"),
                            "amount_est": float(item.get("Amount", 0.0) or 25000.0),
                            "transaction_date": item.get("TransactionDate", ""),
                            "filing_date": item.get("ReportDate", ""),
                            "source": "QuiverQuant"
                        })
        except Exception as e:
            logger.debug(f"QuiverQuant fetch notice: {e}")
            
        # Fallback to CongressInvests if Quiver returned empty
        if not trades:
            recent = self.fetch_congress_invests_ticker(sym) if sym else self.fetch_congress_invests_recent(limit=30)
            for t in recent:
                trades.append({
                    "representative": t.get("member", "Representative"),
                    "chamber": t.get("chamber", "House"),
                    "party": t.get("party", ""),
                    "ticker": t.get("ticker", sym),
                    "transaction_type": t.get("trade_type", "Purchase"),
                    "amount_range": t.get("amount", "$15,001 - $50,000"),
                    "amount_est": float(t.get("amount_num", 25000.0) or 25000.0),
                    "transaction_date": t.get("tx_date", ""),
                    "filing_date": t.get("disclosed", ""),
                    "source": "CongressInvests"
                })
        return trades

    def fetch_institutional_13f_filings(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetches large institutional holdings and 13F-HR filings from SEC EDGAR and Finnhub.
        Free, open-source institutional transparency.
        """
        import requests
        sym = symbol.upper().strip()
        filings = []
        
        headers = {
            "User-Agent": "TradingCockpit research@auton-cockpit.internal",
            "Accept-Encoding": "gzip, deflate"
        }
        sec_url = f"https://efts.sec.gov/LATEST/search-index?q=%22{sym}%22&forms=13F-HR"
        try:
            resp = requests.get(sec_url, headers=headers, timeout=6)
            if resp.status_code == 200:
                hits = resp.json().get("hits", {}).get("hits", [])
                for hit in hits[:20]:
                    src = hit.get("_source", {})
                    display_names = src.get("display_names", [])
                    raw_entity = display_names[0] if display_names else (src.get("entity_name") or "Institutional Fund")
                    entity_clean = raw_entity.split(" (CIK")[0].strip()
                    filings.append({
                        "institution": entity_clean,
                        "filing_type": "13F-HR",
                        "filing_date": src.get("file_date", ""),
                        "period_of_report": src.get("period_ending", ""),
                        "source": "SEC EDGAR 13F-HR"
                    })
        except Exception as e:
            logger.debug(f"SEC 13F fetch {sym}: {e}")
            
        with self._lock:
            self._institutional_cache[sym] = filings
        return filings

    def get_unified_flow_transparency(self, symbol: str, current_price: float = 0.0) -> Dict[str, Any]:
        """
        Merges Finnhub real-time quotes + Quiver Congress trades + Finnhub/SEC 13F institutional flows
        + OpenInsider Form 4 insider trades into a unified transparency flow feed.
        """
        sym = symbol.upper().strip()

        # Real-time stock quote (Finnhub)
        if current_price <= 0.0 and self.finnhub_api_key:
            try:
                import requests as req
                q_res = req.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={self.finnhub_api_key}", timeout=4)
                if q_res.status_code == 200:
                    current_price = float(q_res.json().get("c", 0.0) or 0.0)
            except Exception:
                pass
        
        # 1. Insider Trades (OpenInsider + Finnhub)
        oi_trades = self.fetch_openinsider_trades(sym, limit=20)
        fh_trades = self.fetch_finnhub_insiders(sym)
        all_insiders = oi_trades if oi_trades else fh_trades

        # 2. Congress Trades (QuiverQuant + CongressInvests)
        congress_trades = self.fetch_quiver_congress_trades(sym)

        # 3. Institutional 13F (SEC EDGAR + Finnhub)
        inst_filings = self.fetch_institutional_13f_filings(sym)

        # 4. Compute Flow Conviction
        insider_buys = sum(1 for t in all_insiders if t.get("is_purchase"))
        insider_sells = sum(1 for t in all_insiders if t.get("is_sale"))
        net_insider_val = sum(t.get("value_usd", 0.0) for t in all_insiders)
        
        c_buys = sum(1 for t in congress_trades if "BUY" in str(t.get("transaction_type", "")).upper() or "PURCHASE" in str(t.get("transaction_type", "")).upper())
        c_sells = sum(1 for t in congress_trades if "SELL" in str(t.get("transaction_type", "")).upper() or "SALE" in str(t.get("transaction_type", "")).upper())

        # Baseline conviction
        insider_score = 0.0
        if insider_buys > 0 or insider_sells > 0:
            insider_score = (insider_buys - insider_sells) / max(1, insider_buys + insider_sells)
            if net_insider_val > 500000:
                insider_score += 0.25
            elif net_insider_val < -5000000:
                insider_score -= 0.15

        congress_score = 0.0
        if c_buys > 0 or c_sells > 0:
            congress_score = (c_buys - c_sells) / max(1, c_buys + c_sells)
        elif self.get_congress_conviction(sym) != 0.0:
            congress_score = self.get_congress_conviction(sym)

        inst_score = 0.05 if len(inst_filings) >= 5 else 0.0

        raw_flow = (congress_score * 0.45) + (insider_score * 0.40) + (inst_score * 0.15)
        flow_conviction = round(max(-1.0, min(1.0, raw_flow)), 3)

        flow_sentiment = "BULLISH" if flow_conviction >= 0.10 else ("BEARISH" if flow_conviction <= -0.10 else "NEUTRAL")

        payload = {
            "symbol": sym,
            "price": current_price,
            "flow_conviction": flow_conviction,
            "flow_sentiment": flow_sentiment,
            "congress": congress_trades[:25],
            "institutional": inst_filings[:25],
            "insiders": all_insiders[:25],
            "summary": {
                "net_insider_flow_usd": round(net_insider_val, 2),
                "insider_buys": insider_buys,
                "insider_sells": insider_sells,
                "congress_buys": c_buys,
                "congress_sells": c_sells,
                "institutional_filings_count": len(inst_filings),
                "transparency_score": flow_conviction
            },
            "timestamp": time.time()
        }

        with self._lock:
            self._transparency_feed_cache[sym] = payload

        return payload
