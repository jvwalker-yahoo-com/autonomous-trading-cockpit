"""
NewsIntelligenceEngine — Multi-Source News Aggregator for Autonomous Trading Cockpit.

Sources (every 10 minutes):
  1. RSS Feeds (Yahoo Finance, CNBC, WSJ Markets, MarketWatch, Seeking Alpha)
  2. SEC EDGAR Full-Text Search (8-K material events, Form 4 insider filings)
  3. Finnhub Company News & Earnings Calendar (if FINNHUB_API_KEY is configured)

Outputs a per-symbol CatalystScore (-1.0 to +1.0) and a global MarketSentiment score.
CatalystScore feeds directly into the federation engine's news_sentiment weight and day trading trigger.
"""
import time
import math
import re
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("auton-cockpit.news")

# ── High-Reliability Financial RSS Feeds ────────────────────────────────────
RSS_FEEDS = [
    # Yahoo Finance Top Business & Finance Stories
    "https://finance.yahoo.com/rss/topfinstories",
    # CNBC Markets & Business Breaking News
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    # Wall Street Journal Markets
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    # MarketWatch Top Stories
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    # Seeking Alpha Market Currents
    "https://seekingalpha.com/market_currents.xml",
]

# ── Company Name / Alias Lexicon for Real Financial News Headline Matching ──
COMPANY_ALIASES: Dict[str, List[str]] = {
    "NVDA": ["nvidia", "nvda", "jensen huang", "blackwell", "geforce"],
    "AAPL": ["apple", "aapl", "iphone", "ipad", "macbook", "tim cook"],
    "MSFT": ["microsoft", "msft", "satya nadella", "azure", "windows", "copilot"],
    "TSLA": ["tesla", "tsla", "elon musk", "musk", "cybertruck", "robotaxi", "gigafactory"],
    "META": ["meta", "mark zuckerberg", "zuckerberg", "facebook", "instagram", "threads"],
    "AMZN": ["amazon", "amzn", "andy jassy", "aws", "jeff bezos"],
    "GOOGL": ["alphabet", "google", "googl", "goog", "sundar pichai", "youtube", "gemini"],
    "AMD": ["amd", "advanced micro devices", "lisa su", "mi300", "ryzen"],
    "PLTR": ["palantir", "pltr", "alex karp", "aip platform"],
    "ARM": ["arm holdings", "arm architecture", " arm "],
    "SMCI": ["super micro", "smci", "supermicro"],
    "COIN": ["coinbase", "brian armstrong"],
    "MSTR": ["microstrategy", "mstr", "michael saylor"],
    "HOOD": ["robinhood", "vlad tenev"],
    "SOFI": ["sofi technologies", "sofi", "anthony noto"],
    "ASTS": ["ast spacemobile", "asts"],
    "RKLB": ["rocket lab", "rklb", "peter beck"],
    "LLY": ["eli lilly", "lilly", "zepbound", "mounjaro"],
    "NFLX": ["netflix", "nflx", "reed hastings"],
    "IREN": ["iris energy", "iren"],
    "AVGO": ["broadcom", "avgo", "hock tan"],
    "MARA": ["marathon digital", "mara holdings", "mara"],
    "APLD": ["applied digital", "apld"],
    "BABA": ["alibaba", "baba", "jack ma"],
    "TSM": ["taiwan semi", "tsmc", "tsm"],
    "RIVN": ["rivian", "rivn", "rj scaringe"],
    "UK100": ["ftse", "uk100", "bank of england", "london stock exchange"],
    "GER40": ["dax", "ger40", "bundesbank", "frankfurt"]
}

# ── Bullish / Bearish Sentiment Lexicon ───────────────────────────────────────
BULLISH_WORDS = [
    "beat", "beats", "beating", "surge", "surges", "surging", "rally", "rallies", "rallying",
    "upgrade", "upgraded", "upgrades", "record", "breakthrough", "buyback", "dividend",
    "acquisition", "partnership", "partner", "profit", "profits", "growth", "growing",
    "raise", "raised", "raises", "raising", "exceed", "exceeds", "exceeded", "outperform",
    "outperformed", "buy", "strong", "stronger", "positive", "higher", "gain", "gains",
    "gaining", "approval", "approved", "contract", "awarded", "expansion", "bullish",
    "momentum", "revenue growth", "guidance raised", "eps beat", "analyst upgrade",
    "new high", "all-time high", "soars", "soaring", "jump", "jumps", "jumped"
]

BEARISH_WORDS = [
    "miss", "misses", "missing", "missed", "fall", "falls", "falling", "fell",
    "decline", "declines", "declining", "declined", "downgrade", "downgraded", "downgrades",
    "loss", "losses", "warning", "warns", "risk", "risks", "sell", "selling", "weak",
    "weaker", "weakness", "negative", "lower", "concern", "concerns", "lawsuit", "sued",
    "recall", "investigation", "probe", "fraud", "default", "layoff", "layoffs", "cut",
    "cuts", "cutting", "reduces", "reduced", "disappoints", "disappointing", "disappointed",
    "bearish", "fear", "crash", "crashes", "crashing", "drop", "drops", "dropping",
    "slump", "slumps", "plunge", "plunges", "plunging", "guidance cut", "eps miss",
    "analyst downgrade", "new low", "52-week low", "short seller", "debt", "bankruptcy",
    "fine", "penalty", "subpoena", "rout", "rout"
]

# ── SEC EDGAR Constants ───────────────────────────────────────────────────────
EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"
HIGH_IMPACT_FORMS = {"8-K", "8-K/A", "6-K"}   # Material events
INSIDER_FORMS = {"4", "4/A"}                    # Insider buy/sell


class NewsIntelligenceEngine:
    def __init__(self, finnhub_api_key: str = ""):
        self.finnhub_api_key = finnhub_api_key.strip()
        self._lock = threading.Lock()
        # Per-symbol catalyst scores, keyed by symbol
        self._catalyst_scores: Dict[str, float] = {}
        # Per-symbol news items (last 10 per symbol)
        self._symbol_news: Dict[str, List[Dict[str, Any]]] = {}
        # Global market headlines (last 50)
        self._global_headlines: List[Dict[str, Any]] = []
        # SEC EDGAR filings cache
        self._edgar_cache: Dict[str, List[Dict[str, Any]]] = {}
        # Last full refresh timestamp (-600 triggers immediate run)
        self._last_refresh: float = -600.0
        self._refresh_interval: float = 600.0  # 10 minutes
        # Earnings surprises (symbol -> days_to_earnings)
        self._earnings_calendar: Dict[str, int] = {}
        # Active watchlist
        self._watchlist: List[str] = []

    def set_finnhub_key(self, key: str):
        with self._lock:
            self.finnhub_api_key = key.strip()

    def set_watchlist(self, symbols: List[str]):
        clean = [s.upper().strip() for s in symbols if s.upper().strip() not in (
            "BTC","ETH","SOL","XRP","BNB","DOGE","ADA","AVAX",
            "LINK","DOT","NEAR","MATIC","SHIB","LTC","UNI"
        )]
        with self._lock:
            self._watchlist = clean

    def needs_refresh(self) -> bool:
        return (time.time() - self._last_refresh) >= self._refresh_interval

    # ── Public Accessors ────────────────────────────────────────────────────

    def get_catalyst_score(self, symbol: str) -> float:
        """Returns calibrated catalyst score [-1.0 to +1.0] for a symbol."""
        with self._lock:
            return self._catalyst_scores.get(symbol.upper().strip(), 0.0)

    def get_symbol_news(self, symbol: str) -> List[Dict[str, Any]]:
        """Returns recent news items for a specific symbol."""
        with self._lock:
            return list(self._symbol_news.get(symbol.upper().strip(), []))

    def get_global_headlines(self) -> List[Dict[str, Any]]:
        """Returns recent global market headlines with verified titles."""
        with self._lock:
            return list(self._global_headlines[-30:])

    def get_earnings_alert(self, symbol: str) -> Optional[int]:
        """Returns days to next earnings for symbol, or None."""
        with self._lock:
            return self._earnings_calendar.get(symbol.upper().strip())

    def get_edgar_filings(self, symbol: str) -> List[Dict[str, Any]]:
        """Returns recent SEC EDGAR filings for symbol."""
        with self._lock:
            return list(self._edgar_cache.get(symbol.upper().strip(), []))

    def get_all_scores(self) -> Dict[str, float]:
        """Returns all current catalyst scores."""
        with self._lock:
            return dict(self._catalyst_scores)

    # ── Refresh Orchestrator ────────────────────────────────────────────────

    def refresh_all(self, watchlist: Optional[List[str]] = None):
        """Main refresh entry point — pulls RSS, SEC EDGAR, and Finnhub."""
        import requests
        if watchlist:
            self.set_watchlist(watchlist)

        with self._lock:
            symbols = list(self._watchlist[:30])

        new_scores: Dict[str, float] = {}
        new_news: Dict[str, List[Dict[str, Any]]] = {}
        new_edgar: Dict[str, List[Dict[str, Any]]] = {}
        new_headlines: List[Dict[str, Any]] = []
        new_earnings: Dict[str, int] = {}

        has_finnhub = bool(self.finnhub_api_key and len(self.finnhub_api_key) > 5)

        # 1. Fetch & Parse RSS Feeds (Global news + Watchlist mentions)
        try:
            rss_results = self._fetch_rss_feeds(symbols)
            new_headlines = rss_results["headlines"]

            # Blend RSS sentiment into symbol scores
            rss_weight = 0.30 if has_finnhub else 0.70
            for sym, s_score in rss_results["symbol_scores"].items():
                new_scores[sym] = new_scores.get(sym, 0.0) + s_score * rss_weight

            # Attach symbol-level RSS articles
            for sym, items in rss_results["symbol_news"].items():
                new_news.setdefault(sym, []).extend(items)

            logger.info(f"📰 [NEWS RSS] {len(new_headlines)} headlines fetched across {len(RSS_FEEDS)} feeds")
        except Exception as e:
            logger.warning(f"RSS fetch error: {e}")

        # 2. Finnhub Company News (if configured)
        if has_finnhub:
            for sym in symbols:
                try:
                    score, items = self._fetch_finnhub_news(sym, requests)
                    if items:
                        new_news.setdefault(sym, []).extend(items)
                    new_scores[sym] = new_scores.get(sym, 0.0) + score * 0.40
                    time.sleep(0.25)
                except Exception as e:
                    logger.debug(f"Finnhub news {sym}: {e}")

            # 3. Finnhub Earnings Calendar
            try:
                new_earnings = self._fetch_finnhub_earnings(requests)
                logger.info(f"📅 [EARNINGS] {len(new_earnings)} upcoming earnings dates found")
            except Exception as e:
                logger.debug(f"Finnhub earnings: {e}")

        # 4. SEC EDGAR 8-K & Form 4 Filings (Top 15 symbols)
        edgar_weight = 0.30 if has_finnhub else 0.30
        for sym in symbols[:15]:
            try:
                filings, score = self._fetch_edgar_filings(sym, requests)
                if filings:
                    new_edgar[sym] = filings
                if score != 0.0:
                    new_scores[sym] = new_scores.get(sym, 0.0) + score * edgar_weight
                time.sleep(0.35)
            except Exception as e:
                logger.debug(f"EDGAR {sym}: {e}")

        # 5. Earnings proximity boost: +50% weight if earnings within 3 days
        for sym in list(new_scores.keys()):
            raw = new_scores[sym]
            days = new_earnings.get(sym)
            if days is not None and 0 <= days <= 3:
                raw *= 1.5
                logger.info(f"⚡ [EARNINGS PROXIMITY] {sym} earnings in {days}d — catalyst score boosted")
            new_scores[sym] = round(max(-1.0, min(1.0, raw)), 3)

        # 6. Commit atomically
        with self._lock:
            self._catalyst_scores.update(new_scores)
            self._symbol_news.update(new_news)
            self._edgar_cache.update(new_edgar)
            if new_headlines:
                self._global_headlines = new_headlines[-50:]
            self._earnings_calendar.update(new_earnings)
            self._last_refresh = time.time()

        top_cats = [f"{s}:{v:+.2f}" for s, v in sorted(new_scores.items(), key=lambda x: abs(x[1]), reverse=True)[:8]]
        logger.info(f"🧠 [NEWS INTEL] Refresh complete. Catalysts: {top_cats} | Total headlines: {len(new_headlines)}")

    # ── RSS Feed Fetcher ────────────────────────────────────────────────────

    @staticmethod
    def _el_text(el) -> str:
        """Safely extracts and strips text from an XML element, stripping CDATA."""
        if el is None or el.text is None:
            return ""
        text = el.text.strip()
        if text.startswith("<![CDATA[") and text.endswith("]]>"):
            text = text[9:-3].strip()
        return text

    def _fetch_rss_feeds(self, symbols: List[str]) -> Dict[str, Any]:
        """Parses RSS feeds and matches headlines to watchlist symbols and aliases."""
        import urllib.request
        import xml.etree.ElementTree as ET

        all_headlines: List[Dict[str, Any]] = []
        symbol_mentions: Dict[str, List[float]] = {}
        symbol_news: Dict[str, List[Dict[str, Any]]] = {}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*"
        }

        # Build lookup table of symbol -> compiled word-boundary regex patterns
        sym_patterns: Dict[str, List[re.Pattern]] = {}
        for s in symbols:
            s_up = s.upper()
            aliases = COMPANY_ALIASES.get(s_up, [])
            tokens = [s_up.lower()] + [a.lower().strip() for a in aliases if a.strip()]
            patterns = [re.compile(r'(?:\b|\$)' + re.escape(t.replace('$', '')) + r'\b', re.IGNORECASE) for t in tokens if t]
            sym_patterns[s_up] = patterns

        for feed_url in RSS_FEEDS:
            try:
                req = urllib.request.Request(feed_url, headers=headers)
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw = resp.read().decode("utf-8", errors="ignore")

                root = ET.fromstring(raw)
                items = root.findall(".//item")
                if not items:
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                source_name = feed_url.split("/")[2].replace("www.", "")

                for item in items[:25]:
                    title, desc, link, pub = "", "", "", ""
                    for child in item:
                        tag = child.tag.lower().split("}")[-1]
                        if tag == "title" and not title:
                            title = self._el_text(child)
                        elif tag in ("description", "summary") and not desc:
                            desc = self._el_text(child)
                        elif tag == "link" and not link:
                            link = self._el_text(child) or child.attrib.get("href", "")
                        elif tag in ("pubdate", "published", "updated") and not pub:
                            pub = self._el_text(child)

                    # Strictly ignore items without a readable title
                    if not title or len(title) < 5:
                        continue

                    # Clean HTML tags from description if present
                    clean_desc = re.sub(r"<[^>]+>", "", desc).strip()
                    text = f"{title} {clean_desc}".lower()

                    score = self._score_text(text)

                    # Match symbols via word-boundary regex patterns
                    matched = []
                    for sym_up, patterns in sym_patterns.items():
                        if any(p.search(text) for p in patterns):
                            matched.append(sym_up)
                            symbol_mentions.setdefault(sym_up, []).append(score)
                            symbol_news.setdefault(sym_up, []).append({
                                "title": title[:200],
                                "source": source_name,
                                "score": round(score, 2),
                                "url": link,
                                "published": pub,
                                "category": "RSS Financial News"
                            })

                    all_headlines.append({
                        "title": title[:200],
                        "score": round(score, 2),
                        "source": source_name,
                        "url": link,
                        "published": pub,
                        "symbols": matched,
                    })

            except Exception as e:
                logger.debug(f"RSS feed notice ({feed_url}): {e}")

        # Compute average catalyst score per symbol
        symbol_scores: Dict[str, float] = {}
        for sym, scores in symbol_mentions.items():
            if scores:
                avg = sum(scores) / len(scores)
                # Boost if multiple independent mentions
                mention_mult = min(1.5, 1.0 + (len(scores) - 1) * 0.15)
                symbol_scores[sym] = round(max(-1.0, min(1.0, avg * mention_mult)), 3)

        return {
            "headlines": all_headlines,
            "symbol_scores": symbol_scores,
            "symbol_news": symbol_news
        }

    # ── Finnhub Company News ────────────────────────────────────────────────

    def _fetch_finnhub_news(self, symbol: str, requests_mod) -> Tuple[float, List[Dict[str, Any]]]:
        """Fetches Finnhub company news for the last 3 days."""
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
        for art in articles[:10]:
            h_line = art.get("headline", "") or ""
            summ = art.get("summary", "") or ""
            text = f"{h_line} {summ}".lower()
            score = self._score_text(text)
            total_score += score
            items.append({
                "title": h_line[:200],
                "source": art.get("source", "Finnhub"),
                "score": round(score, 2),
                "url": art.get("url", ""),
                "published": art.get("datetime", 0),
                "category": art.get("category", "Company News"),
            })

        avg_score = (total_score / len(articles)) if articles else 0.0
        return round(max(-1.0, min(1.0, avg_score)), 3), items

    # ── Finnhub Earnings Calendar ───────────────────────────────────────────

    def _fetch_finnhub_earnings(self, requests_mod) -> Dict[str, int]:
        """Returns {symbol: days_to_earnings} for upcoming 7 days."""
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
            sym = str(item.get("symbol", "")).upper()
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

    def _fetch_edgar_filings(self, symbol: str, requests_mod) -> Tuple[List[Dict[str, Any]], float]:
        """Fetches recent 8-K material events and Form 4 insider transactions."""
        headers = {
            "User-Agent": "TradingCockpit research@auton-cockpit.internal",
            "Accept-Encoding": "gzip, deflate",
        }

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
                for hit in hits[:5]:
                    src = hit.get("_source", {})
                    form = src.get("form_type", "")
                    filed = src.get("file_date", "")
                    entity = src.get("entity_name", symbol)
                    description = src.get("period_of_report", "")

                    filing_score = 0.0
                    label = form

                    if form in HIGH_IMPACT_FORMS:
                        text_snippet = src.get("description", "") or src.get("file_date", "")
                        filing_score = self._score_text(str(text_snippet).lower()) * 0.5
                        label = f"8-K Material Event ({description})"
                    elif form in INSIDER_FORMS:
                        text = str(src).lower()
                        if "purchase" in text or "acquired" in text:
                            filing_score = 0.30
                            label = f"Form 4: Insider BUY by {entity}"
                        elif "sale" in text or "disposed" in text:
                            filing_score = -0.10
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

    # ── Text Sentiment Scorer ───────────────────────────────────────────────

    def _score_text(self, text: str) -> float:
        """Scores text sentiment on scale of -1.0 to +1.0 using financial keyword density."""
        text_lower = text.lower()
        bull = sum(1 for w in BULLISH_WORDS if w in text_lower)
        bear = sum(1 for w in BEARISH_WORDS if w in text_lower)
        if bull == 0 and bear == 0:
            return 0.0
        raw = (bull - bear) / max(1, bull + bear + 1)
        return round(max(-1.0, min(1.0, raw * 2.0)), 3)
