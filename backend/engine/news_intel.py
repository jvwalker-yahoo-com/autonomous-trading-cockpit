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
    # BBC World Business Breaking News
    "https://feeds.bbci.co.uk/news/business/rss.xml",
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

# ── Macro Theme Categories & Keyword Lexicon ─────────────────────────────────
MACRO_THEMES: Dict[str, List[str]] = {
    "CENTRAL_BANKS_RATES": [
        "interest rate", "rate cut", "rate hike", "federal reserve", "fed", "jerome powell",
        "powell", "ecb", "lagarde", "bank of england", "boe", "inflation", "cpi", "ppi",
        "treasury yields", "treasuries", "bond yields", "monetary policy", "quantitative", "central bank"
    ],
    "GEOPOLITICS_CONFLICT": [
        "war", "military", "missile", "sanction", "sanctions", "tariff", "tariffs", "trade war",
        "taiwan", "china tension", "middle east", "iran", "israel", "russia", "ukraine",
        "strait of hormuz", "red sea", "geopolitical", "national security", "defense", "ceasefire"
    ],
    "ENERGY_COMMODITIES": [
        "crude oil", "brent", "wti", "opec", "natural gas", "oil prices", "energy crisis",
        "uranium", "gold", "silver", "copper", "petroleum", "gas pipeline"
    ],
    "AI_TECH_REGULATION": [
        "antitrust", "doj", "ftc", "eu ai act", "export control", "chip ban", "semiconductor restrictions",
        "big tech probe", "ai regulation", "patent infringement", "ai chip export", "deepseek"
    ],
    "SYSTEMIC_RECESSION": [
        "recession", "credit default", "banking crisis", "yield curve inversion", "gdp contraction",
        "liquidity crisis", "contagion", "debt ceiling", "default risk", "insolvency", "layoffs"
    ]
}

HIGH_IMPACT_MACRO_KEYWORDS: List[str] = [
    "war", "attack", "missile", "crash", "plunge", "emergency", "crisis", "sanction",
    "default", "rate shock", "embargo", "surge", "all-time high", "bankruptcy",
    "tariff threat", "black swan", "halt", "halted", "recession confirmed", "ceasefire"
]

# ── SEC EDGAR Constants ───────────────────────────────────────────────────────
EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"
HIGH_IMPACT_FORMS = {"8-K", "8-K/A", "6-K"}   # Material events
INSIDER_FORMS = {"4", "4/A"}                    # Insider buy/sell


class NewsIntelligenceEngine:
    def __init__(
        self,
        finnhub_api_key: str = "",
        alpha_vantage_api_key: str = "",
        tavily_api_key: str = "",
        serpapi_api_key: str = ""
    ):
        self.finnhub_api_key = finnhub_api_key.strip()
        self.alpha_vantage_api_key = alpha_vantage_api_key.strip()
        self.tavily_api_key = tavily_api_key.strip()
        self.serpapi_api_key = serpapi_api_key.strip()
        self._lock = threading.Lock()
        # Per-symbol catalyst scores, keyed by symbol
        self._catalyst_scores: Dict[str, float] = {}
        # Per-symbol news items (last 10 per symbol)
        self._symbol_news: Dict[str, List[Dict[str, Any]]] = {}
        # Global market headlines (last 50)
        self._global_headlines: List[Dict[str, Any]] = []
        # Worldwide breaking news stream
        self._world_breaking_news: List[Dict[str, Any]] = []
        # Macro posture telemetry
        self._macro_sentiment: float = 0.0
        self._macro_risk_level: str = "NORMAL"
        self._macro_themes: List[Dict[str, Any]] = []
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

    def set_feed_keys(self, finnhub_key: str = "", alpha_vantage_key: str = "", tavily_key: str = "", serpapi_key: str = ""):
        with self._lock:
            if finnhub_key:
                self.finnhub_api_key = finnhub_key.strip()
            if alpha_vantage_key:
                self.alpha_vantage_api_key = alpha_vantage_key.strip()
            if tavily_key:
                self.tavily_api_key = tavily_key.strip()
            if serpapi_key:
                self.serpapi_key = serpapi_key.strip()


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

    def get_world_breaking_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns verified live worldwide breaking market news articles."""
        with self._lock:
            return list(self._world_breaking_news[:limit])

    def get_macro_risk_state(self) -> Dict[str, Any]:
        """Returns consolidated global macro risk posture and top themes."""
        with self._lock:
            return {
                "macro_sentiment": self._macro_sentiment,
                "macro_risk_level": self._macro_risk_level,
                "macro_themes": list(self._macro_themes),
                "breaking_news_count": len(self._world_breaking_news),
                "last_refresh": self._last_refresh,
            }

    # ── Refresh Orchestrator ────────────────────────────────────────────────

    def refresh_all(self, watchlist: Optional[List[str]] = None):
        """Main refresh entry point — pulls RSS, SEC EDGAR, Finnhub, SerpApi, and Tavily."""
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

        # 5. Tavily AI Search Catalysts (Breaking financial news)
        if self.tavily_api_key and len(self.tavily_api_key) > 5:
            try:
                t_scores, t_news = self._fetch_tavily_catalysts(symbols[:10], requests)
                for sym, t_score in t_scores.items():
                    new_scores[sym] = new_scores.get(sym, 0.0) + t_score * 0.25
                for sym, items in t_news.items():
                    new_news.setdefault(sym, []).extend(items)
                if t_scores:
                    logger.info(f"🔎 [TAVILY INTEL] Scanned {len(t_scores)} symbols for breaking catalyst news")
            except Exception as e:
                logger.debug(f"Tavily catalyst error: {e}")

        # 6. Alpha Vantage News & Sentiment (Targeted catalysts)
        if self.alpha_vantage_api_key and len(self.alpha_vantage_api_key) > 5:
            try:
                av_scores, av_news = self._fetch_alpha_vantage_sentiment(symbols[:5], requests)
                for sym, av_score in av_scores.items():
                    new_scores[sym] = new_scores.get(sym, 0.0) + av_score * 0.25
                for sym, items in av_news.items():
                    new_news.setdefault(sym, []).extend(items)
                if av_scores:
                    logger.info(f"📈 [ALPHA VANTAGE INTEL] Sentiment extracted for {len(av_scores)} symbols")
            except Exception as e:
                logger.debug(f"Alpha Vantage sentiment error: {e}")

        # 7. Earnings proximity boost: +50% weight if earnings within 3 days
        for sym in list(new_scores.keys()):
            raw = new_scores[sym]
            days = new_earnings.get(sym)
            if days is not None and 0 <= days <= 3:
                raw *= 1.5
                logger.info(f"⚡ [EARNINGS PROXIMITY] {sym} earnings in {days}d — catalyst score boosted")
            new_scores[sym] = round(max(-1.0, min(1.0, raw)), 3)


        # 8. Worldwide Breaking News & Macro Posture (Finnhub, SerpApi, Tavily, RSS)
        new_world_news: List[Dict[str, Any]] = []
        new_macro_sentiment: float = 0.0
        new_macro_risk_level: str = "NORMAL"
        new_macro_themes: List[Dict[str, Any]] = []
        try:
            new_world_news, new_macro_sentiment, new_macro_risk_level, new_macro_themes = self._fetch_global_market_news(
                requests, existing_rss_headlines=new_headlines
            )
            logger.info(
                f"🌍 [WORLD NEWS INTEL] {len(new_world_news)} breaking articles ingested | "
                f"Macro Risk: {new_macro_risk_level} (Sentiment: {new_macro_sentiment:+.2f})"
            )
        except Exception as e:
            logger.warning(f"Global news fetch error: {e}")

        # 9. Commit atomically
        with self._lock:
            self._catalyst_scores.update(new_scores)
            self._symbol_news.update(new_news)
            self._edgar_cache.update(new_edgar)
            if new_headlines:
                self._global_headlines = new_headlines[-50:]
            if new_world_news:
                self._world_breaking_news = new_world_news[:100]
                self._macro_sentiment = new_macro_sentiment
                self._macro_risk_level = new_macro_risk_level
                self._macro_themes = new_macro_themes
            self._earnings_calendar.update(new_earnings)
            self._last_refresh = time.time()

        top_cats = [f"{s}:{v:+.2f}" for s, v in sorted(new_scores.items(), key=lambda x: abs(x[1]), reverse=True)[:8]]
        logger.info(f"🧠 [NEWS INTEL] Refresh complete. Catalysts: {top_cats} | Total headlines: {len(new_headlines)} | World news: {len(new_world_news)}")

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
        raw = (bull - bear) / max(1, bull + bear)
        return round(max(-1.0, min(1.0, raw * 2.0)), 3)

    # ── Global Macro News Intelligence & Theme Classifier ─────────────────────

    def _classify_macro_article(
        self,
        title: str,
        summary: str = "",
        source: str = "",
        url: str = "",
        pub_time: float = 0.0
    ) -> Dict[str, Any]:
        """Classifies a global macro news article into theme, sentiment, severity, and impacted assets."""
        full_text = f"{title} {summary}".strip().lower()
        score = self._score_text(full_text)

        # Determine theme
        theme_counts: Dict[str, int] = {}
        for theme, keywords in MACRO_THEMES.items():
            cnt = sum(1 for kw in keywords if kw in full_text)
            if cnt > 0:
                theme_counts[theme] = cnt

        if theme_counts:
            best_theme = max(theme_counts.items(), key=lambda x: x[1])[0]
        else:
            best_theme = "MACRO_GLOBAL"

        # Determine sentiment label
        if score >= 0.08:
            sentiment = "BULLISH"
        elif score <= -0.08:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        # Severity classification
        high_severity = any(kw in full_text for kw in HIGH_IMPACT_MACRO_KEYWORDS) or abs(score) >= 0.40
        if high_severity:
            severity = "HIGH"
        elif abs(score) >= 0.20 or best_theme in ("CENTRAL_BANKS_RATES", "GEOPOLITICS_CONFLICT"):
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Identify impacted assets & tickers
        affected = set()
        for sym, aliases in COMPANY_ALIASES.items():
            for alias in aliases:
                if alias in full_text:
                    affected.add(sym)
                    break

        if any(w in full_text for w in ["oil", "brent", "wti", "opec", "energy", "petroleum"]):
            affected.add("ENERGY")
        if any(w in full_text for w in ["chip", "semiconductor", "gpu", "ai hardware", "foundry"]):
            affected.add("SEMIS")
        if any(w in full_text for w in ["interest rate", "fed", "inflation", "powell", "treasury", "yield"]):
            affected.add("SPY")
            affected.add("QQQ")
        if any(w in full_text for w in ["ftse", "uk economy", "bank of england", "britain", "london"]):
            affected.add("UK100")
        if any(w in full_text for w in ["dax", "german", "germany", "bundesbank", "european union", "ecb"]):
            affected.add("GER40")

        import hashlib
        art_id = hashlib.md5((title + source).encode("utf-8")).hexdigest()[:10]

        return {
            "id": art_id,
            "title": title.strip(),
            "summary": summary.strip()[:280] if summary else "",
            "source": source or "Global Wire",
            "url": url,
            "time": pub_time or time.time(),
            "theme": best_theme,
            "sentiment": sentiment,
            "score": score,
            "severity": severity,
            "affected_assets": sorted(list(affected))[:5]
        }

    def _fetch_global_market_news(
        self,
        requests_mod,
        existing_rss_headlines: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[Dict[str, Any]], float, str, List[Dict[str, Any]]]:
        """
        Ingests worldwide breaking news across Finnhub general market wire,
        SerpApi Google News, Tavily AI Search, and high-impact RSS items.
        Returns: (articles, macro_sentiment, macro_risk_level, macro_themes)
        """
        all_articles: List[Dict[str, Any]] = []
        seen_titles = set()

        def _add_article(item: Dict[str, Any]):
            # Deduplicate by first 35 alphanumeric characters
            norm = re.sub(r'[^a-zA-Z0-9]', '', item.get("title", "").lower())[:35]
            if norm and norm not in seen_titles:
                seen_titles.add(norm)
                all_articles.append(item)

        # 1. Finnhub General Market News Wire (Reuters, Bloomberg, CNBC)
        if self.finnhub_api_key and len(self.finnhub_api_key) > 5:
            try:
                fh_url = f"https://finnhub.io/api/v1/news?category=general&token={self.finnhub_api_key}"
                resp = requests_mod.get(fh_url, timeout=6)
                if resp.status_code == 200:
                    fh_items = resp.json()
                    if isinstance(fh_items, list):
                        for art in fh_items[:45]:
                            title = art.get("headline", "")
                            if not title or len(title) < 8:
                                continue
                            classified = self._classify_macro_article(
                                title=title,
                                summary=art.get("summary", ""),
                                source=art.get("source", "Finnhub/Reuters"),
                                url=art.get("url", ""),
                                pub_time=float(art.get("datetime", time.time()))
                            )
                            _add_article(classified)
            except Exception as e:
                logger.debug(f"Finnhub general news error: {e}")

        # 2. SerpApi Google News Breaking Market Stories
        if self.serpapi_api_key and len(self.serpapi_api_key) > 5:
            try:
                serp_url = (
                    f"https://serpapi.com/search.json"
                    f"?engine=google_news&q=global+financial+markets+stocks+breaking+news&api_key={self.serpapi_api_key}"
                )
                resp = requests_mod.get(serp_url, timeout=7)
                if resp.status_code == 200:
                    news_results = resp.json().get("news_results", [])
                    for r in news_results[:25]:
                        title = r.get("title", "")
                        if not title or len(title) < 8:
                            continue
                        source_obj = r.get("source", {})
                        source_name = source_obj.get("name", "Google News") if isinstance(source_obj, dict) else "Google News"
                        snippet = r.get("snippet", "")
                        pub_iso = r.get("date", "")
                        pub_ts = time.time()
                        classified = self._classify_macro_article(
                            title=title,
                            summary=snippet,
                            source=source_name,
                            url=r.get("link", ""),
                            pub_time=pub_ts
                        )
                        _add_article(classified)
            except Exception as e:
                logger.debug(f"SerpApi Google News error: {e}")

        # 3. Tavily AI Search for Worldwide Macro Catalysts
        if self.tavily_api_key and len(self.tavily_api_key) > 5:
            try:
                tav_resp = requests_mod.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": "breaking global stock markets economy news central bank rates trade tariffs",
                        "search_depth": "basic",
                        "max_results": 6
                    },
                    timeout=6
                )
                if tav_resp.status_code == 200:
                    for r in tav_resp.json().get("results", []):
                        title = r.get("title", "")
                        if not title or len(title) < 8:
                            continue
                        classified = self._classify_macro_article(
                            title=title,
                            summary=r.get("content", ""),
                            source="Tavily AI Macro",
                            url=r.get("url", ""),
                            pub_time=time.time()
                        )
                        _add_article(classified)
            except Exception as e:
                logger.debug(f"Tavily macro news error: {e}")

        # 4. Ingest Global RSS Headlines (BBC Business, Yahoo, etc.)
        if existing_rss_headlines:
            for h in existing_rss_headlines[:35]:
                title = h.get("title", "")
                if not title or len(title) < 8:
                    continue
                classified = self._classify_macro_article(
                    title=title,
                    summary="",
                    source=h.get("source", "RSS Feed"),
                    url=h.get("url", ""),
                    pub_time=time.time()
                )
                _add_article(classified)

        # Sort by timestamp descending
        all_articles.sort(key=lambda x: x.get("time", 0.0), reverse=True)

        # Calculate Macro Sentiment and Risk Posture
        if all_articles:
            scores = [a["score"] for a in all_articles]
            macro_sentiment = round(sum(scores) / len(scores), 3)
            high_bear_count = sum(1 for a in all_articles if a.get("severity") == "HIGH" and a.get("sentiment") == "BEARISH")
            bear_count = sum(1 for a in all_articles if a.get("sentiment") == "BEARISH")
            bull_count = sum(1 for a in all_articles if a.get("sentiment") == "BULLISH")

            if high_bear_count >= 3 or macro_sentiment <= -0.30:
                macro_risk_level = "CRITICAL"
            elif high_bear_count >= 1 or macro_sentiment <= -0.12 or (bear_count > bull_count * 1.6 and bear_count >= 8):
                macro_risk_level = "ELEVATED"
            elif macro_sentiment >= 0.18:
                macro_risk_level = "FAVORABLE"
            else:
                macro_risk_level = "NORMAL"
        else:
            macro_sentiment = 0.0
            macro_risk_level = "NORMAL"

        # Group Macro Themes
        theme_groups: Dict[str, List[float]] = {}
        for a in all_articles:
            theme_groups.setdefault(a["theme"], []).append(a["score"])

        macro_themes = []
        for theme_name, theme_scores in sorted(theme_groups.items(), key=lambda x: len(x[1]), reverse=True):
            avg_sc = round(sum(theme_scores) / len(theme_scores), 2)
            macro_themes.append({
                "theme": theme_name,
                "count": len(theme_scores),
                "sentiment": avg_sc,
                "label": "BULLISH" if avg_sc > 0.05 else ("BEARISH" if avg_sc < -0.05 else "NEUTRAL")
            })

        return all_articles, macro_sentiment, macro_risk_level, macro_themes

    # ── Tavily & Alpha Vantage News Intelligence ─────────────────────────────

    def _fetch_tavily_catalysts(self, symbols: List[str], requests_mod) -> Tuple[Dict[str, float], Dict[str, List[Dict[str, Any]]]]:
        """Queries Tavily AI Search for breaking catalyst news on watchlist symbols."""
        if not self.tavily_api_key or len(self.tavily_api_key) < 5:
            return {}, {}
        scores: Dict[str, float] = {}
        news_map: Dict[str, List[Dict[str, Any]]] = {}
        for sym in symbols[:10]:
            try:
                resp = requests_mod.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": f"{sym} stock news catalyst analyst earnings",
                        "search_depth": "basic",
                        "max_results": 3
                    },
                    timeout=6
                )
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    sym_score = 0.0
                    for r in results:
                        title = r.get("title", "")
                        content = r.get("content", "")
                        text = (title + " " + content).lower()
                        b_score = sum(1 for w in BULLISH_WORDS if w in text)
                        be_score = sum(1 for w in BEARISH_WORDS if w in text)
                        diff = b_score - be_score
                        sym_score += max(-1.0, min(1.0, diff / 4.0))
                        news_map.setdefault(sym, []).append({
                            "title": title,
                            "url": r.get("url", ""),
                            "source": "Tavily AI News",
                            "time": time.time(),
                            "sentiment": "BULLISH" if diff > 0 else ("BEARISH" if diff < 0 else "NEUTRAL")
                        })
                    if results:
                        scores[sym] = round(max(-1.0, min(1.0, sym_score / len(results))), 3)
            except Exception as e:
                logger.debug(f"Tavily catalyst {sym}: {e}")
        return scores, news_map

    def _fetch_alpha_vantage_sentiment(self, symbols: List[str], requests_mod) -> Tuple[Dict[str, float], Dict[str, List[Dict[str, Any]]]]:
        """Queries Alpha Vantage NEWS_SENTIMENT endpoint for targeted tickers."""
        if not self.alpha_vantage_api_key or len(self.alpha_vantage_api_key) < 5:
            return {}, {}
        scores: Dict[str, float] = {}
        news_map: Dict[str, List[Dict[str, Any]]] = {}
        for sym in symbols[:5]:
            try:
                url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={sym}&limit=5&apikey={self.alpha_vantage_api_key}"
                resp = requests_mod.get(url, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    feed = data.get("feed", [])
                    if feed:
                        sent_scores = []
                        for item in feed:
                            for t in item.get("ticker_sentiment", []):
                                if t.get("ticker") == sym:
                                    try:
                                        sent_scores.append(float(t.get("ticker_sentiment_score", 0.0)))
                                    except Exception:
                                        pass
                            news_map.setdefault(sym, []).append({
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "source": item.get("source", "Alpha Vantage"),
                                "time": time.time(),
                                "sentiment": item.get("overall_sentiment_label", "NEUTRAL")
                            })
                        if sent_scores:
                            scores[sym] = round(sum(sent_scores) / len(sent_scores), 3)
            except Exception as e:
                logger.debug(f"Alpha Vantage sentiment {sym}: {e}")
        return scores, news_map

