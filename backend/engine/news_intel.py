"""
NewsIntelligenceEngine — Multi-Source News Aggregator for Autonomous Trading Cockpit.

Sources (every 10 minutes):
  1. Finnhub Company News API (free tier: last 7 days headlines per symbol)
  2. Finnhub Earnings Calendar (upcoming earnings surprises)
  3. SEC EDGAR EDGAR Full-Text Search (8-K material events, Form 4 insider filings)
  4. RSS Feeds: Reuters Business, MarketWatch, Seeking Alpha, Motley Fool, Yahoo Finance

Outputs a per-symbol CatalystScore (-1.0 to +1.0) and a global MarketSentiment score.
CatalystScore feeds directly into the federation engine's news_sentiment weight.
"""
import time
import math
import re
import logging
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("auton-cockpit.news")

# ── RSS Feed URLs (public, no auth needed) ──────────────────────────────────
RSS_FEEDS = [
    # Reuters Business
    "https://feeds.reuters.com/reuters/businessNews",
    # MarketWatch
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    # Yahoo Finance
    "https://finance.yahoo.com/rss/topfinstories",
    # Seeking Alpha Market News
    "https://seekingalpha.com/market_currents.xml",
    # Motley Fool
    "https://www.fool.com/feeds/index.aspx",
    # CNBC Top News
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    # Investopedia
    "https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_headline",
]

# ── Bullish / Bearish keyword lexicon ───────────────────────────────────────
BULLISH_WORDS = [
    "beat", "beats", "surge", "surges", "rally", "rallies", "upgrade", "upgraded",
    "record", "breakthrough", "buyback", "dividend", "acquisition", "partnership",
    "profit", "growth", "raise", "raised", "exceed", "exceeds", "outperform",
    "buy", "strong", "positive", "higher", "gain", "gains", "approval", "approved",
    "contract", "awarded", "expansion", "bullish", "momentum", "revenue growth",
    "guidance raised", "eps beat", "analyst upgrade", "new high", "all-time high",
]
BEARISH_WORDS = [
    "miss", "misses", "fall", "falls", "decline", "declines", "downgrade", "downgraded",
    "loss", "losses", "warning", "risk", "sell", "weak", "negative", "lower",
    "concern", "concerns", "lawsuit", "recall", "investigation", "fraud", "default",
    "layoff", "layoffs", "cut", "reduces", "disappoints", "bearish", "fear", "crash",
    "guidance cut", "eps miss", "analyst downgrade", "new low", "52-week low",
    "short seller", "debt", "bankruptcy", "fine", "penalty", "subpoena",
]

# ── SEC EDGAR API ────────────────────────────────────────────────────────────
EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"

# High-impact SEC form types
HIGH_IMPACT_FORMS = {"8-K", "8-K/A", "6-K"}   # Material events
INSIDER_FORMS = {"4", "4/A"}                    # Insider buy/sell


class NewsIntelligenceEngine:
    def __init__(self, finnhub_api_key: str = ""):
        self.finnhub_api_key = finnhub_api_key
        self._lock = threading.Lock()
        # Per-symbol catalyst scores, keyed by symbol
        self._catalyst_scores: Dict[str, float] = {}
        # Per-symbol news items (last 10 per symbol)
        self._symbol_news: Dict[str, List[Dict]] = {}
        # Global market headlines
        self._global_headlines: List[Dict] = []
        # SEC EDGAR filings cache
        self._edgar_cache: Dict[str, List[Dict]] = {}
        # Last full refresh timestamp
        self._last_refresh: float = 0.0
        self._refresh_interval: float = 600.0  # 10 minutes
        # Earnings surprises (symbol -> days_to_earnings)
        self._earnings_calendar: Dict[str, int] = {}
        # Active watchlist to focus fetches on
        self._watchlist: List[str] = []

    def set_finnhub_key(self, key: str):
        self.finnhub_api_key = key.strip()

    def set_watchlist(self, symbols: List[str]):
        self._watchlist = [s for s in symbols if s not in (
            "BTC","ETH","SOL","XRP","BNB","DOGE","ADA","AVAX",
            "LINK","DOT","NEAR","MATIC","SHIB","LTC","UNI",
        )]

    def needs_refresh(self) -> bool:
        return (time.time() - self._last_refresh) >= self._refresh_interval

    # ── Public API ──────────────────────────────────────────────────────────

    def get_catalyst_score(self, symbol: str) -> float:
        """Returns calibrated catalyst score [-1, +1] for a symbol."""
        with self._lock:
            return self._catalyst_scores.get(symbol, 0.0)

    def get_symbol_news(self, symbol: str) -> List[Dict]:
        """Returns recent news items for a symbol."""
        with self._lock:
            return list(self._symbol_news.get(symbol, []))

    def get_global_headlines(self) -> List[Dict]:
        """Returns recent global market headlines."""
        with self._lock:
            return list(self._global_headlines[-20:])

    def get_earnings_alert(self, symbol: str) -> Optional[int]:
        """Returns days to next earnings for symbol, or None."""
        with self._lock:
            return self._earnings_calendar.get(symbol)

    def get_edgar_filings(self, symbol: str) -> List[Dict]:
        """Returns recent SEC EDGAR filings for symbol."""
        with self._lock:
            return list(self._edgar_cache.get(symbol, []))

    def get_all_scores(self) -> Dict[str, float]:
        """Returns all current catalyst scores."""
        with self._lock:
            return dict(self._catalyst_scores)

    # ── Refresh (called from background loop every 10 min) ──────────────────

    def refresh_all(self, watchlist: Optional[List[str]] = None):
        """Main refresh entry point — fetches all sources and updates scores."""
        import requests
        if watchlist:
            self.set_watchlist(watchlist)

        symbols = self._watchlist[:30]  # Limit to top 30 to respect rate limits
        new_scores: Dict[str, float] = {}
        new_news: Dict[str, List[Dict]] = {}
        new_edgar: Dict[str, List[Dict]] = {}
        new_headlines: List[Dict] = []
        new_earnings: Dict[str, int] = {}

        # 1. RSS Feeds (global market sentiment + symbol mentions)
        try:
            rss_results = self._fetch_rss_feeds(symbols)
            new_headlines = rss_results["headlines"]
            for sym in symbols:
                if sym in rss_results["symbol_scores"]:
                    new_scores[sym] = new_scores.get(sym, 0.0) + rss_results["symbol_scores"][sym] * 0.25
            logger.info(f"📰 [NEWS RSS] {len(new_headlines)} headlines fetched")
        except Exception as e:
            logger.warning(f"RSS fetch error: {e}")

        # 2. Finnhub Company News per symbol
        if self.finnhub_api_key and len(self.finnhub_api_key) > 5:
            for sym in symbols:
                try:
                    score, items = self._fetch_finnhub_news(sym, requests)
                    new_news[sym] = items
                    new_scores[sym] = new_scores.get(sym, 0.0) + score * 0.40
                    time.sleep(0.3)  # Respect Finnhub rate limit (30 calls/min free tier)
                except Exception as e:
                    logger.debug(f"Finnhub news {sym}: {e}")

            # 3. Finnhub Earnings Calendar
            try:
                new_earnings = self._fetch_finnhub_earnings(requests)
                logger.info(f"📅 [EARNINGS] {len(new_earnings)} upcoming earnings found")
            except Exception as e:
                logger.debug(f"Finnhub earnings: {e}")

        # 4. SEC EDGAR — 8-K filings and insider Form 4 for each symbol
        for sym in symbols[:15]:  # EDGAR is slow; limit to top 15
            try:
                filings, score = self._fetch_edgar_filings(sym, requests)
                new_edgar[sym] = filings
                if score != 0.0:
                    new_scores[sym] = new_scores.get(sym, 0.0) + score * 0.35
                time.sleep(0.5)  # EDGAR rate limit: 10 req/sec
            except Exception as e:
                logger.debug(f"EDGAR {sym}: {e}")

        # 5. Clamp all scores to [-1, +1] and apply earnings proximity boost
        for sym in list(new_scores.keys()):
            raw = new_scores[sym]
            # Earnings proximity booster: score *= 1.5 if earnings within 3 days
            days = new_earnings.get(sym)
            if days is not None and 0 <= days <= 3:
                raw = raw * 1.5
                logger.info(f"⚡ [EARNINGS PROXIMITY] {sym} earnings in {days}d — catalyst score boosted")
            new_scores[sym] = round(max(-1.0, min(1.0, raw)), 3)

        # 6. Commit results atomically
        with self._lock:
            self._catalyst_scores.update(new_scores)
            self._symbol_news.update(new_news)
            self._edgar_cache.update(new_edgar)
            self._global_headlines = new_headlines[-50:]
            self._earnings_calendar.update(new_earnings)
            self._last_refresh = time.time()

        scored = [f"{s}:{v:+.2f}" for s, v in sorted(new_scores.items(), key=lambda x: abs(x[1]), reverse=True)[:8]]
        logger.info(f"🧠 [NEWS INTEL] Refresh complete. Top catalysts: {scored}")

    # ── RSS Feed Fetcher ────────────────────────────────────────────────────

    def _fetch_rss_feeds(self, symbols: List[str]) -> Dict:
        """Parses RSS feeds and scores headlines by symbol mention."""
        import urllib.request
        import xml.etree.ElementTree as ET

        all_headlines = []
        symbol_scores: Dict[str, float] = {}
        sym_lower = {s.lower(): s for s in symbols}

        for feed_url in RSS_FEEDS:
            try:
                req = urllib.request.Request(
                    feed_url,
                    headers={"User-Agent": "TradingCockpit/2.0 (+research)"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    raw = resp.read().decode("utf-8", errors="ignore")

                root = ET.fromstring(raw)
                # Handle both RSS and Atom formats
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall(".//item") or root.findall(".//atom:entry", ns)

                for item in items[:20]:  # Max 20 items per feed
                    title_el = item.find("title") or item.find("atom:title", ns)
                    desc_el = item.find("description") or item.find("atom:summary", ns)
                    link_el = item.find("link") or item.find("atom:link", ns)
                    pub_el = item.find("pubDate") or item.find("atom:updated", ns)

                    title = (title_el.text or "") if title_el is not None else ""
                    desc = (desc_el.text or "") if desc_el is not None else ""
                    link = (link_el.text or (link_el.get("href", "") if link_el is not None else "")) if link_el is not None else ""
                    pub = (pub_el.text or "") if pub_el is not None else ""

                    text = f"{title} {desc}".lower()
                    score = self._score_text(text)

                    headline = {
                        "title": title[:200],
                        "score": score,
                        "source": feed_url.split("/")[2],
                        "url": link,
                        "published": pub,
                        "symbols": [],
                    }

                    # Check which symbols are mentioned
                    for sym_l, sym in sym_lower.items():
                        if sym_l in text or f"${sym_l}" in text:
                            headline["symbols"].append(sym)
                            prev = symbol_scores.get(sym, 0.0)
                            symbol_scores[sym] = prev + score

                    all_headlines.append(headline)

            except Exception as e:
                logger.debug(f"RSS {feed_url}: {e}")

        # Normalize symbol scores by mention count
        for sym in symbol_scores:
            symbol_scores[sym] = max(-1.0, min(1.0, symbol_scores[sym] / 3.0))

        return {"headlines": all_headlines, "symbol_scores": symbol_scores}

    # ── Finnhub News Fetcher ────────────────────────────────────────────────

    def _fetch_finnhub_news(self, symbol: str, requests_mod) -> Tuple[float, List[Dict]]:
        """Fetches Finnhub company news and returns (score, items)."""
        from_date = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = (
            f"https://finnhub.io/api/v1/company-news"
            f"?symbol={symbol}&from={from_date}&to={to_date}&token={self.finnhub_api_key}"
        )
        resp = requests_mod.get(url, timeout=4)
        if resp.status_code != 200:
            return 0.0, []

        articles = resp.json()
        if not isinstance(articles, list):
            return 0.0, []

        items = []
        total_score = 0.0
        for art in articles[:10]:  # Process last 10 articles
            text = f"{art.get('headline', '')} {art.get('summary', '')}".lower()
            score = self._score_text(text)
            total_score += score
            items.append({
                "title": art.get("headline", "")[:200],
                "source": art.get("source", ""),
                "score": round(score, 2),
                "url": art.get("url", ""),
                "published": art.get("datetime", 0),
                "category": art.get("category", ""),
            })

        avg_score = (total_score / len(articles)) if articles else 0.0
        return round(max(-1.0, min(1.0, avg_score)), 3), items

    # ── Finnhub Earnings Calendar ───────────────────────────────────────────

    def _fetch_finnhub_earnings(self, requests_mod) -> Dict[str, int]:
        """Returns {symbol: days_to_earnings} for upcoming 7-day earnings."""
        from_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        to_date = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
        url = (
            f"https://finnhub.io/api/v1/calendar/earnings"
            f"?from={from_date}&to={to_date}&token={self.finnhub_api_key}"
        )
        resp = requests_mod.get(url, timeout=4)
        if resp.status_code != 200:
            return {}

        data = resp.json()
        result = {}
        today = datetime.now(timezone.utc).date()
        for item in data.get("earningsCalendar", []):
            sym = item.get("symbol", "").upper()
            date_str = item.get("date", "")
            if sym and date_str:
                try:
                    earn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    days = (earn_date - today).days
                    if 0 <= days <= 7:
                        result[sym] = days
                except Exception:
                    pass
        return result

    # ── SEC EDGAR Fetcher ───────────────────────────────────────────────────

    def _fetch_edgar_filings(self, symbol: str, requests_mod) -> Tuple[List[Dict], float]:
        """
        Fetches recent 8-K (material events) and Form 4 (insider trades) from SEC EDGAR.
        Returns (filings_list, catalyst_score_contribution).
        """
        headers = {
            "User-Agent": "TradingCockpit research@example.com",
            "Accept-Encoding": "gzip, deflate",
        }

        # Search EDGAR for recent filings for this symbol
        search_url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{symbol}%22"
            f"&dateRange=custom&startdt={(datetime.now(timezone.utc) - timedelta(days=5)).strftime('%Y-%m-%d')}"
            f"&enddt={datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            f"&forms=8-K,4"
        )

        filings = []
        score = 0.0

        try:
            resp = requests_mod.get(search_url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])
                for hit in hits[:5]:  # Last 5 filings
                    src = hit.get("_source", {})
                    form = src.get("form_type", "")
                    filed = src.get("file_date", "")
                    entity = src.get("entity_name", symbol)
                    description = src.get("period_of_report", "")

                    filing_score = 0.0
                    label = form

                    if form in HIGH_IMPACT_FORMS:
                        # 8-K: material event — check filing text snippet for sentiment
                        text_snippet = src.get("description", "") or src.get("file_date", "")
                        filing_score = self._score_text(str(text_snippet).lower()) * 0.5
                        label = f"8-K Material Event ({description})"
                    elif form in INSIDER_FORMS:
                        # Form 4: insider transaction
                        # Insider buys are bullish (+0.3), sells are bearish (-0.1)
                        text = str(src).lower()
                        if "purchase" in text or "acquired" in text:
                            filing_score = 0.30
                            label = f"Form 4: Insider BUY by {entity}"
                        elif "sale" in text or "disposed" in text:
                            filing_score = -0.10  # Sells are less bearish (routine)
                            label = f"Form 4: Insider SELL by {entity}"

                    score += filing_score
                    filings.append({
                        "form": form,
                        "label": label,
                        "entity": entity,
                        "filed": filed,
                        "score": round(filing_score, 2),
                    })
        except Exception as e:
            logger.debug(f"EDGAR search {symbol}: {e}")

        return filings, round(max(-1.0, min(1.0, score)), 3)

    # ── Text Scorer ────────────────────────────────────────────────────────

    def _score_text(self, text: str) -> float:
        """Scores a text string based on bullish/bearish keyword count."""
        text_lower = text.lower()
        bull = sum(1 for w in BULLISH_WORDS if w in text_lower)
        bear = sum(1 for w in BEARISH_WORDS if w in text_lower)
        raw = (bull - bear) / max(1, bull + bear + 1)
        return round(max(-1.0, min(1.0, raw * 2.0)), 3)
