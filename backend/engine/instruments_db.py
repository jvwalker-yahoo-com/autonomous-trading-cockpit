"""
SQLite Instruments Database Engine for eToro Trading.
Provides fast ticker-to-ID resolution, persistent storage, dynamic discovery caching,
and automated nightly catalog updates.
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("instruments.db")

# Default database location inside the project's data directory
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "instruments.db"

# Master Seed Instruments covering all 100+ multi-asset instruments on eToro
INITIAL_SEED_INSTRUMENTS: List[Dict[str, Any]] = [
    # === 1. CRYPTOCURRENCIES (24/7 Continuous Trading) ===
    {"symbol": "BTC", "instrument_id": 100000, "name": "Bitcoin", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "ETH", "instrument_id": 100001, "name": "Ethereum", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "XRP", "instrument_id": 100002, "name": "Ripple", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "LTC", "instrument_id": 100003, "name": "Litecoin", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "ADA", "instrument_id": 100004, "name": "Cardano", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "DOGE", "instrument_id": 100005, "name": "Dogecoin", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "SOL", "instrument_id": 100006, "name": "Solana", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "DOT", "instrument_id": 100007, "name": "Polkadot", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "AVAX", "instrument_id": 100010, "name": "Avalanche", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "MATIC", "instrument_id": 100011, "name": "Polygon", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "LINK", "instrument_id": 100012, "name": "Chainlink", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "UNI", "instrument_id": 100013, "name": "Uniswap", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "ATOM", "instrument_id": 100014, "name": "Cosmos", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "FTM", "instrument_id": 100015, "name": "Fantom", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "NEAR", "instrument_id": 100016, "name": "NEAR Protocol", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "SUI", "instrument_id": 100020, "name": "Sui", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "FET", "instrument_id": 100021, "name": "Artificial Superintelligence Alliance", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "BNB", "instrument_id": 100022, "name": "Binance Coin", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "RENDER", "instrument_id": 100023, "name": "Render Token", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "SHIB", "instrument_id": 100024, "name": "Shiba Inu", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},
    {"symbol": "PEPE", "instrument_id": 100025, "name": "Pepe", "category": "Crypto", "asset_class": "Crypto", "trading_hours": "24/7"},

    # === 2. US EQUITIES (Tech, AI, Growth & Blue Chips) ===
    {"symbol": "AAPL", "instrument_id": 1001, "name": "Apple Inc", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "MSFT", "instrument_id": 1002, "name": "Microsoft Corp", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "GOOGL", "instrument_id": 1003, "name": "Alphabet Inc", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "AMZN", "instrument_id": 1004, "name": "Amazon.com Inc", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "TSLA", "instrument_id": 1005, "name": "Tesla Inc", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "META", "instrument_id": 1006, "name": "Meta Platforms", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "NVDA", "instrument_id": 1007, "name": "NVIDIA Corp", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "NFLX", "instrument_id": 1008, "name": "Netflix Inc", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "AMD", "instrument_id": 1009, "name": "Advanced Micro Devices", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "INTC", "instrument_id": 1010, "name": "Intel Corp", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "AVGO", "instrument_id": 1012, "name": "Broadcom Inc", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "PLTR", "instrument_id": 1014, "name": "Palantir Technologies", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "ARM", "instrument_id": 1015, "name": "Arm Holdings", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "SMCI", "instrument_id": 1016, "name": "Super Micro Computer", "category": "AI & Tech Titans", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "IREN", "instrument_id": 1017, "name": "Iris Energy", "category": "Crypto Runners", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "COIN", "instrument_id": 1018, "name": "Coinbase Global", "category": "Crypto Runners", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "MSTR", "instrument_id": 1019, "name": "MicroStrategy Inc", "category": "Crypto Runners", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "HOOD", "instrument_id": 1020, "name": "Robinhood Markets", "category": "Fintech & Growth", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "SOFI", "instrument_id": 1021, "name": "SoFi Technologies", "category": "Fintech & Growth", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "RIVN", "instrument_id": 1022, "name": "Rivian Automotive", "category": "EVs & Clean Tech", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "ASTS", "instrument_id": 1023, "name": "AST SpaceMobile", "category": "Space & Defense", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "RKLB", "instrument_id": 1024, "name": "Rocket Lab USA", "category": "Space & Defense", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "BABA", "instrument_id": 1025, "name": "Alibaba Group", "category": "Global Blue Chips", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "TSM", "instrument_id": 1026, "name": "Taiwan Semiconductor", "category": "Global Blue Chips", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "LLY", "instrument_id": 1027, "name": "Eli Lilly and Co", "category": "Global Blue Chips", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "CRWD", "instrument_id": 1028, "name": "CrowdStrike Holdings", "category": "Cybersecurity", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "CLSK", "instrument_id": 1029, "name": "CleanSpark Inc", "category": "Crypto Runners", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "MARA", "instrument_id": 1051, "name": "Marathon Digital", "category": "Crypto Runners", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "APLD", "instrument_id": 1052, "name": "Applied Digital", "category": "Crypto Runners", "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},

    # === 3. BENCHMARK & LEVERAGED ETFS ===
    {"symbol": "SPY", "instrument_id": 2001, "name": "SPDR S&P 500 ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "QQQ", "instrument_id": 2002, "name": "Invesco QQQ Trust", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "SQQQ", "instrument_id": 2003, "name": "ProShares UltraPro Short QQQ", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "FNGU", "instrument_id": 2004, "name": "MicroSectors FANG+ 3X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "SOXL", "instrument_id": 2005, "name": "Direxion Semiconductor Bull 3X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "UPRO", "instrument_id": 2006, "name": "ProShares UltraPro S&P500 3X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "IWM", "instrument_id": 2007, "name": "iShares Russell 2000 ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "DIA", "instrument_id": 2008, "name": "SPDR Dow Jones Industrial", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "VOO", "instrument_id": 2009, "name": "Vanguard S&P 500 ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "VTI", "instrument_id": 2010, "name": "Vanguard Total Stock Market", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "SOXS", "instrument_id": 2011, "name": "Direxion Semi Bear 3X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "TQQQ", "instrument_id": 2012, "name": "ProShares UltraPro QQQ 3X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "BULL", "instrument_id": 2013, "name": "Direxion S&P 500 Bull 3X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "NVDL", "instrument_id": 2014, "name": "GraniteShares 2X Long NVDA", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "TSLL", "instrument_id": 2015, "name": "Direxion Daily TSLA Bull 2X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "LABU", "instrument_id": 2016, "name": "Direxion Biotech Bull 3X", "category": "Leveraged ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "SMH", "instrument_id": 2017, "name": "VanEck Semiconductor ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "XLK", "instrument_id": 2018, "name": "Technology Select SPDR", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "XLF", "instrument_id": 2019, "name": "Financial Select SPDR", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "XLE", "instrument_id": 2020, "name": "Energy Select SPDR", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "XLV", "instrument_id": 2021, "name": "Health Care Select SPDR", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "XLI", "instrument_id": 2022, "name": "Industrial Select SPDR", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "XBI", "instrument_id": 2023, "name": "SPDR S&P Biotech ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "URA", "instrument_id": 2024, "name": "Global X Uranium ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "ARKK", "instrument_id": 2025, "name": "ARK Innovation ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "GDX", "instrument_id": 2026, "name": "VanEck Gold Miners ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "TAN", "instrument_id": 2027, "name": "Invesco Solar ETF", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    {"symbol": "TLT", "instrument_id": 2028, "name": "iShares 20+ Year Treasury", "category": "ETFs", "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},

    # === 4. BENCHMARK INDICES ===
    {"symbol": "SPX500", "instrument_id": 2100, "name": "S&P 500 Index", "category": "Indices", "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "NDX100", "instrument_id": 2101, "name": "Nasdaq 100 Index", "category": "Indices", "asset_class": "Index", "trading_hours": "24/7 (Break 22:00-23:00)"},
    {"symbol": "NSDQ100", "instrument_id": 2101, "name": "Nasdaq 100 Index", "category": "Indices", "asset_class": "Index", "trading_hours": "24/7 (Break 22:00-23:00)"},
    {"symbol": "DJ30", "instrument_id": 2102, "name": "Dow Jones 30", "category": "Indices", "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "GER40", "instrument_id": 2103, "name": "Germany DAX 40", "category": "Indices", "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    {"symbol": "UK100", "instrument_id": 2104, "name": "FTSE 100 (UK)", "category": "Indices", "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    {"symbol": "AUS200", "instrument_id": 2105, "name": "ASX 200 (Australia)", "category": "Indices", "asset_class": "Index", "trading_hours": "Mon 01:00 - Fri 07:00 UK"},
    {"symbol": "FRA40", "instrument_id": 2106, "name": "CAC 40 (France)", "category": "Indices", "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    {"symbol": "ESP35", "instrument_id": 2107, "name": "IBEX 35 (Spain)", "category": "Indices", "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    {"symbol": "JPN225", "instrument_id": 2108, "name": "Nikkei 225 (Japan)", "category": "Indices", "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "HKG50", "instrument_id": 2109, "name": "Hang Seng (Hong Kong)", "category": "Indices", "asset_class": "Index", "trading_hours": "Mon 01:15 - Fri 08:00 UK"},
    {"symbol": "RUSSELL2000", "instrument_id": 2110, "name": "Russell 2000 Index", "category": "Indices", "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "USDOLLAR", "instrument_id": 2111, "name": "US Dollar Index (DXY)", "category": "Indices", "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "VIX", "instrument_id": 2112, "name": "CBOE Volatility Index", "category": "Indices", "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},

    # === 5. COMMODITIES (Metals, Energy, Agriculture) ===
    {"symbol": "GOLD", "instrument_id": 3001, "name": "Gold (Spot Non-Expiry)", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "24/7 (Break 22:00-23:00)"},
    {"symbol": "SILVER", "instrument_id": 3002, "name": "Silver (Spot Non-Expiry)", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "OIL", "instrument_id": 3003, "name": "Crude Oil (Brent/WTI)", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "NGAS", "instrument_id": 3004, "name": "Natural Gas", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "NATGAS", "instrument_id": 3004, "name": "Natural Gas (alias)", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "COPPER", "instrument_id": 3005, "name": "Copper (Non-Expiry)", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "PLATINUM", "instrument_id": 3006, "name": "Platinum", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "PALLADIUM", "instrument_id": 3007, "name": "Palladium", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "GASOLINE", "instrument_id": 3008, "name": "RBOB Gasoline", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "SUGAR", "instrument_id": 3009, "name": "Sugar", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 08:30 - Fri 18:00 UK"},
    {"symbol": "SUGAR.FUT", "instrument_id": 3009, "name": "Sugar Futures", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 08:30 - Fri 18:00 UK"},
    {"symbol": "COTTON", "instrument_id": 3010, "name": "Cotton", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 02:00 - Fri 19:20 UK"},
    {"symbol": "COTTON.FUT", "instrument_id": 3010, "name": "Cotton Futures", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 02:00 - Fri 19:20 UK"},
    {"symbol": "COCOA", "instrument_id": 3011, "name": "Cocoa", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 09:45 - Fri 18:30 UK"},
    {"symbol": "COCOA.FUT", "instrument_id": 3011, "name": "Cocoa Futures", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 09:45 - Fri 18:30 UK"},
    {"symbol": "COFFEE", "instrument_id": 3012, "name": "Coffee", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 09:15 - Fri 18:30 UK"},
    {"symbol": "COFFEE.FUT", "instrument_id": 3012, "name": "Coffee Futures", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Mon 09:15 - Fri 18:30 UK"},
    {"symbol": "WHEAT", "instrument_id": 3013, "name": "Wheat", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "WHEAT.FUT", "instrument_id": 3013, "name": "Wheat Futures", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "CORN", "instrument_id": 3014, "name": "Corn", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    {"symbol": "CORN.FUT", "instrument_id": 3014, "name": "Corn Futures", "category": "Commodities", "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
]


class InstrumentsDBManager:
    """Manages SQLite database for eToro ticker-to-ID mapping and nightly synchronization."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_if_empty()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with WAL mode enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging (WAL) for smooth concurrent read/write access
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self):
        """Initializes tables and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS instruments (
                    symbol TEXT PRIMARY KEY,
                    instrument_id INTEGER NOT NULL,
                    name TEXT,
                    category TEXT,
                    asset_class TEXT,
                    trading_hours TEXT,
                    is_active INTEGER DEFAULT 1,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_instruments_id ON instruments(instrument_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_instruments_cat ON instruments(category);")
            conn.commit()

    def _seed_if_empty(self):
        """Seeds master universe instruments if table is empty or sparsely populated."""
        with self._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) as cnt FROM instruments;").fetchone()["cnt"]
            if count < len(INITIAL_SEED_INSTRUMENTS):
                logger.info(f"[InstrumentsDB] Seeding {len(INITIAL_SEED_INSTRUMENTS)} master universe tickers into SQLite...")
                now_str = datetime.now(timezone.utc).isoformat()
                for inst in INITIAL_SEED_INSTRUMENTS:
                    conn.execute("""
                        INSERT OR REPLACE INTO instruments 
                        (symbol, instrument_id, name, category, asset_class, trading_hours, is_active, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        inst["symbol"].upper().strip(),
                        int(inst["instrument_id"]),
                        inst.get("name", inst["symbol"]),
                        inst.get("category", "General"),
                        inst.get("asset_class", "Stock"),
                        inst.get("trading_hours", "eToro Hours"),
                        1,
                        now_str
                    ))
                conn.commit()
                logger.info(f"✓ [InstrumentsDB] Pre-seeded SQLite database at {self.db_path} ({len(INITIAL_SEED_INSTRUMENTS)} assets).")

    def get_etoro_id(self, symbol: str) -> Optional[int]:
        """
        Primary Lookup Function:
        Returns the eToro internal instrument ID for a ticker symbol.
        Normalizes aliases (e.g. 'CORN.FUT' -> 'CORN').
        """
        if not symbol or not isinstance(symbol, str):
            return None
        
        sym = symbol.strip().upper()

        with self._get_connection() as conn:
            # 1. Direct exact lookup
            row = conn.execute("SELECT instrument_id FROM instruments WHERE symbol = ?;", (sym,)).fetchone()
            if row:
                return int(row["instrument_id"])
            
            # 2. Alias resolution: handle .FUT or exchange extensions like .US
            clean_sym = sym.replace(".FUT", "").replace(".US", "")
            row = conn.execute("SELECT instrument_id FROM instruments WHERE symbol = ?;", (clean_sym,)).fetchone()
            if row:
                # Cache the alias in DB for subsequent zero-cost lookups
                conn.execute("""
                    INSERT OR IGNORE INTO instruments (symbol, instrument_id, name, category, asset_class, trading_hours, is_active)
                    VALUES (?, ?, ?, 'Alias', 'Derived', 'eToro Hours', 1);
                """, (sym, int(row["instrument_id"]), f"Alias of {clean_sym}"))
                conn.commit()
                return int(row["instrument_id"])

        return None

    def get_instrument(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Returns full metadata for an instrument from SQLite."""
        if not symbol:
            return None
        sym = symbol.strip().upper()
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM instruments WHERE symbol = ?;", (sym,)).fetchone()
            if row:
                return dict(row)
            # Try without .FUT
            clean_sym = sym.replace(".FUT", "")
            row = conn.execute("SELECT * FROM instruments WHERE symbol = ?;", (clean_sym,)).fetchone()
            if row:
                return dict(row)
        return None

    def upsert_instrument(
        self,
        symbol: str,
        instrument_id: int,
        name: Optional[str] = None,
        category: Optional[str] = None,
        asset_class: Optional[str] = None,
        trading_hours: Optional[str] = None,
        is_active: int = 1
    ) -> bool:
        """Inserts or updates an instrument record in SQLite."""
        sym = symbol.strip().upper()
        now_str = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO instruments 
                    (symbol, instrument_id, name, category, asset_class, trading_hours, is_active, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    sym,
                    int(instrument_id),
                    name or sym,
                    category or "General",
                    asset_class or "Stock",
                    trading_hours or "eToro Hours",
                    is_active,
                    now_str
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[InstrumentsDB] Upsert error for {sym}: {e}")
            return False

    def list_all_instruments(self, category: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Returns all registered instruments, optionally filtered by category."""
        with self._get_connection() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM instruments WHERE category = ? ORDER BY symbol ASC LIMIT ?;",
                    (category, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM instruments ORDER BY symbol ASC LIMIT ?;",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def search_instruments(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Performs search by symbol or name."""
        q = f"%{query.strip().upper()}%"
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM instruments 
                WHERE symbol LIKE ? OR UPPER(name) LIKE ? 
                ORDER BY CASE WHEN symbol = ? THEN 1 WHEN symbol LIKE ? THEN 2 ELSE 3 END, symbol ASC 
                LIMIT ?;
            """, (q, q, query.strip().upper(), f"{query.strip().upper()}%", limit)).fetchall()
            return [dict(r) for r in rows]

    def count(self) -> int:
        """Returns total instruments in database."""
        with self._get_connection() as conn:
            return conn.execute("SELECT COUNT(*) as cnt FROM instruments;").fetchone()["cnt"]

    def sync_from_etoro(self, etoro_client=None) -> Dict[str, Any]:
        """
        Nightly Synchronization Routine (Scheduled at 10:00 PM UK time):
        Pulls newly discovered instruments from portfolio positions, watchlist,
        and authenticated market data to update the SQLite database.
        """
        logger.info(f"🔄 [InstrumentsDB Nightly Sync] Starting catalog update at {datetime.now(timezone.utc).isoformat()}...")
        new_count = 0
        updated_count = 0

        # 1. Sync from internal seed and verified mappings
        for inst in INITIAL_SEED_INSTRUMENTS:
            sym = inst["symbol"].upper()
            existing = self.get_etoro_id(sym)
            if existing is None:
                self.upsert_instrument(
                    symbol=sym,
                    instrument_id=inst["instrument_id"],
                    name=inst.get("name"),
                    category=inst.get("category"),
                    asset_class=inst.get("asset_class"),
                    trading_hours=inst.get("trading_hours")
                )
                new_count += 1
            elif existing != inst["instrument_id"]:
                self.upsert_instrument(
                    symbol=sym,
                    instrument_id=inst["instrument_id"],
                    name=inst.get("name"),
                    category=inst.get("category"),
                    asset_class=inst.get("asset_class"),
                    trading_hours=inst.get("trading_hours")
                )
                updated_count += 1

        # 2. If etoro_client is configured and provided, discover live account positions & watchlists
        if etoro_client and hasattr(etoro_client, "is_configured") and etoro_client.is_configured():
            try:
                # Sync user's open portfolio positions to discover verified active IDs
                discovered = etoro_client.populate_cache_from_portfolio()
                if discovered > 0:
                    for sym, iid in getattr(etoro_client, "_instrument_cache", {}).items():
                        if not self.get_etoro_id(sym):
                            self.upsert_instrument(symbol=sym, instrument_id=iid, name=f"{sym} (Portfolio Position)")
                            new_count += 1
            except Exception as e:
                logger.warning(f"[InstrumentsDB Sync] Portfolio discovery notice: {e}")

            try:
                # Attempt to query eToro watchlists to discover items
                watchlists = etoro_client.get_user_watchlists()
                for wl in watchlists:
                    items = wl.get("items") or wl.get("WatchlistItems") or []
                    for it in items:
                        if isinstance(it, dict):
                            sym = (it.get("symbol") or it.get("itemSymbol") or it.get("internalSymbolFull") or "").upper()
                            iid = it.get("instrumentId") or it.get("itemId")
                            if sym and iid and not self.get_etoro_id(sym):
                                self.upsert_instrument(symbol=sym, instrument_id=int(iid), name=f"{sym} (Watchlist)")
                                new_count += 1
            except Exception as e:
                logger.warning(f"[InstrumentsDB Sync] Watchlist discovery notice: {e}")

        total_now = self.count()
        logger.info(f"✅ [InstrumentsDB Nightly Sync Complete] Added {new_count} new, updated {updated_count}. Total registered in SQLite: {total_now}.")
        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_instruments_added": new_count,
            "instruments_updated": updated_count,
            "total_instruments": total_now
        }


# Singleton manager instance
_instruments_db_instance: Optional[InstrumentsDBManager] = None

def get_instruments_db() -> InstrumentsDBManager:
    """Returns singleton InstrumentsDBManager instance."""
    global _instruments_db_instance
    if _instruments_db_instance is None:
        _instruments_db_instance = InstrumentsDBManager()
    return _instruments_db_instance

def get_etoro_id(symbol: str) -> Optional[int]:
    """
    Public module function:
    Returns the eToro internal instrument ID for any ticker symbol using SQLite.
    Example: get_etoro_id("BTC") -> 100000, get_etoro_id("AAPL") -> 1001.
    """
    return get_instruments_db().get_etoro_id(symbol)
