import time
import random
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from .models import HeartbeatOutput, SyncDriftOutput

# Complete eToro UK Global Multi-Asset Trading Schedule (Civil UK London Time GMT+1/BST)
ETORO_EXCHANGES_UK: Dict[str, Dict[str, Any]] = {
    # 1. STOCKS & ETFS (US Equities)
    "US_EQUITIES": {
        "name": "NYSE / NASDAQ / CBOE / OTC",
        "category": "Stocks & ETFs",
        "description": "US Equities & Leveraged ETFs (MARA, SOXL, TQQQ, NVDA, SPY, MSFT, META, etc.)",
        "days": [0, 1, 2, 3, 4], # Mon - Fri
        "open_time_uk": (14, 30), # 14:30 UK (2:30 PM)
        "close_time_uk": (21, 0),  # 21:00 UK (9:00 PM)
        "daily_break": "21:00 - 14:30 UK",
        "symbols": ["MARA", "IREN", "SOXL", "TQQQ", "MSFT", "META", "APLD", "SPY", "QQQ", "BULL", "URA", "HOOD", "SOFI", "NVDA", "AAPL", "TSLA", "AMZN", "GOOGL"]
    },
    "LSE": {
        "name": "London Stock Exchange (LSE)",
        "category": "Stocks & ETFs",
        "description": "UK Equities & FTSE constituents",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (8, 0),
        "close_time_uk": (16, 30),
        "daily_break": "16:30 - 08:00 UK",
        "symbols": [".L", "LSE", "LON"]
    },
    "EUROPE_EQUITIES": {
        "name": "Frankfurt / Euronext / Madrid",
        "category": "Stocks & ETFs",
        "description": "European Stocks & XETRA ETFs",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (8, 0),
        "close_time_uk": (16, 30),
        "daily_break": "16:30 - 08:00 UK",
        "symbols": [".DE", ".PA", ".AS", ".MC"]
    },
    
    # 2. COMMODITIES
    "GOLD": {
        "name": "Gold (Non-Expiry)",
        "category": "Commodities",
        "description": "Spot Gold CFD (24/7 continuous with short daily maintenance)",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "open_time_uk": (0, 0),
        "close_time_uk": (24, 0),
        "daily_break": "Daily 22:00 - 23:00 UK",
        "symbols": ["GOLD", "XAUUSD"]
    },
    "COMMODITIES_METALS_ENERGY": {
        "name": "Oil / Silver / NatGas / Copper / Platinum",
        "category": "Commodities",
        "description": "Energy & Industrial Metals (Sun 23:00 to Fri 21:30 UK)",
        "days": [0, 1, 2, 3, 4, 6], # Sun 23:00 - Fri 21:30
        "open_time_uk": (0, 0),
        "close_time_uk": (22, 0),
        "daily_break": "Daily 22:00 - 23:00 UK",
        "symbols": ["OIL", "SILVER", "COPPER", "NATGAS", "PLATINUM", "PALLADIUM", "COPPER.FUT", "PALLADIUM.FUT"]
    },
    "COMMODITIES_AGRI": {
        "name": "Sugar / Cotton / Cocoa (Futures)",
        "category": "Commodities",
        "description": "Agricultural Commodities",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (8, 30),
        "close_time_uk": (18, 0),
        "daily_break": "Daily 18:00 - 08:30 UK",
        "symbols": ["SUGAR.FUT", "COTTON.FUT", "COCOA.FUT", "SUGAR", "COTTON", "COCOA"]
    },

    # 3. INDICES
    "INDICES_US": {
        "name": "SPX500 / NSDQ100 / DJ30 / US Dollar Index",
        "category": "Indices",
        "description": "Major US & Global Benchmark Indices",
        "days": [0, 1, 2, 3, 4, 6], # Sun 23:00 - Fri 21:30
        "open_time_uk": (0, 0),
        "close_time_uk": (22, 0),
        "daily_break": "Daily 22:00 - 23:00 UK",
        "symbols": ["SPX500", "NSDQ100", "DJ30", "USDOLLAR", "JPN225"]
    },
    "INDICES_UK_EU": {
        "name": "UK100 / GER40 / FRA40 / ESP35 / AUS200",
        "category": "Indices",
        "description": "European & Pacific Benchmark Indices",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (1, 0),
        "close_time_uk": (21, 0),
        "daily_break": "Daily 21:00 - 01:00 UK",
        "symbols": ["UK100", "GER40", "FRA40", "ESP35", "AUS200"]
    },

    # 4. CURRENCIES (FOREX)
    "FOREX": {
        "name": "Currencies (FX Pairs)",
        "category": "Forex",
        "description": "EUR/USD, GBP/USD, USD/JPY, etc. (Continuous Sun 23:05 - Fri 22:30 UK)",
        "days": [0, 1, 2, 3, 4, 6], # Sun 23:05 to Fri 22:30
        "open_time_uk": (0, 0),
        "close_time_uk": (23, 0),
        "daily_break": "Daily 23:00 - 23:05 UK",
        "symbols": ["EURUSD", "USDJPY", "GBPUSD", "USDCHF", "NZDUSD", "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY"]
    },

    # 5. FUTURES (CME Micro & Spot Quoted)
    "FUTURES": {
        "name": "Micro Futures (CME)",
        "category": "Futures",
        "description": "Micro E-mini Indices, Oil, Gold, Natural Gas, Crypto Futures (Mon 02:08 - Fri 21:59 GMT)",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (2, 8),
        "close_time_uk": (21, 59),
        "daily_break": "Daily 21:59 - 02:08 GMT",
        "symbols": ["MICRO", "FUT", "FUTURE", "ES_F", "NQ_F", "CL_F", "GC_F", "SI_F", "NG_F"]
    },

    # 6. CRYPTOCURRENCIES
    "CRYPTO": {
        "name": "Cryptocurrencies",
        "category": "Crypto",
        "description": "24/7 Digital Asset Trading (BTC, ETH, SOL, XRP, etc.)",
        "days": [0, 1, 2, 3, 4, 5, 6], # 24/7 Continuous
        "open_time_uk": (0, 0),
        "close_time_uk": (24, 0),
        "daily_break": "None (Continuous 24/7)",
        "symbols": [
            "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX",
            "LINK", "DOT", "NEAR", "MATIC", "SHIB", "LTC", "UNI",
            "RENDER", "FET", "SUI", "PEPE"
        ]
    }
}

ALL_CRYPTO_SET = {
    "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX",
    "LINK", "DOT", "NEAR", "MATIC", "SHIB", "LTC", "UNI",
    "RENDER", "FET", "SUI", "PEPE"
}

class TelemetryModule:
    def __init__(self):
        self.start_time = time.time()

    def heartbeat(self) -> HeartbeatOutput:
        """
        alive = true
        timestamp = time.now()
        """
        uptime = time.time() - self.start_time
        return HeartbeatOutput(
            alive=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
            uptime_seconds=round(uptime, 1),
            status="healthy"
        )

    def get_exchange_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """Resolves target eToro UK schedule for any asset class."""
        sym = symbol.upper()
        
        # Crypto check
        if any(sym == c or sym.startswith(c) for c in ALL_CRYPTO_SET):
            if not ("FUTURE" in sym or "MICRO" in sym):
                return ETORO_EXCHANGES_UK["CRYPTO"]

        # Forex check
        if any(fx in sym for fx in ("EURUSD", "USDJPY", "GBPUSD", "USDCHF", "NZDUSD", "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY")):
            return ETORO_EXCHANGES_UK["FOREX"]

        # Gold check
        if sym in ("GOLD", "XAUUSD"):
            return ETORO_EXCHANGES_UK["GOLD"]

        # Commodities check
        if any(cm in sym for cm in ("OIL", "SILVER", "COPPER", "NATGAS", "PLATINUM", "PALLADIUM")):
            return ETORO_EXCHANGES_UK["COMMODITIES_METALS_ENERGY"]
        if any(ag in sym for ag in ("SUGAR", "COTTON", "COCOA")):
            return ETORO_EXCHANGES_UK["COMMODITIES_AGRI"]

        # Indices check
        if any(idx in sym for idx in ("SPX500", "NSDQ100", "DJ30", "USDOLLAR", "JPN225")):
            return ETORO_EXCHANGES_UK["INDICES_US"]
        if any(idx in sym for idx in ("UK100", "GER40", "FRA40", "ESP35", "AUS200")):
            return ETORO_EXCHANGES_UK["INDICES_UK_EU"]

        # Futures check
        if any(f in sym for f in ("MICRO", "FUT", "FUTURE")):
            return ETORO_EXCHANGES_UK["FUTURES"]

        # LSE / UK Equities check
        if sym.endswith(".L") or sym.endswith(".LON"):
            return ETORO_EXCHANGES_UK["LSE"]

        # European Equities check
        if any(sym.endswith(ext) for ext in (".DE", ".PA", ".AS", ".MC", ".LS")):
            return ETORO_EXCHANGES_UK["EUROPE_EQUITIES"]

        # Default: US Equities & Leveraged ETFs (MARA, SOXL, TQQQ, NVDA, SPY, etc.)
        return ETORO_EXCHANGES_UK["US_EQUITIES"]

    def is_etoro_uk_market_open(self, symbol: str = "SPY") -> Tuple[bool, str]:
        """
        Validates whether eToro UK trading session is open for the specified asset.
        Computes current UK local time (accounting for BST/GMT offset).
        """
        now_utc = datetime.now(timezone.utc)
        # UK is UTC+1 during BST (British Summer Time, last Sunday March to last Sunday Oct)
        month = now_utc.month
        is_bst = 3 < month < 10 or (month == 3 and now_utc.day >= 25) or (month == 10 and now_utc.day <= 25)
        uk_hour = (now_utc.hour + (1 if is_bst else 0)) % 24
        uk_minute = now_utc.minute
        weekday = now_utc.weekday() # 0 = Mon, 4 = Fri, 5 = Sat, 6 = Sun

        exch = self.get_exchange_for_symbol(symbol)
        
        # Check active trading days
        if weekday not in exch["days"]:
            return False, f"Market Closed (Weekend: {exch['name']} opens next active session)"

        open_h, open_m = exch["open_time_uk"]
        close_h, close_m = exch["close_time_uk"]

        current_mins = uk_hour * 60 + uk_minute
        open_mins = open_h * 60 + open_m
        close_mins = close_h * 60 + close_m

        if close_h == 24: # 24/7 continuous
            return True, f"eToro UK Session Active ({exch['name']} 24/7)"

        if current_mins < open_mins:
            mins_left = open_mins - current_mins
            hrs = mins_left // 60
            mins = mins_left % 60
            return False, f"Pre-Market (Opens at {open_h:02d}:{open_m:02d} UK in {hrs}h {mins}m)"
        elif current_mins >= close_mins:
            return False, f"Market Closed ({exch['name']} closed at {close_h:02d}:{close_m:02d} UK)"
        else:
            return True, f"eToro UK Active Session ({open_h:02d}:{open_m:02d} - {close_h:02d}:{close_m:02d} UK)"


    def sync_drift(self) -> SyncDriftOutput:
        """
        drift_ms = random(0..250) (or microsecond clock variance)
        status = "OK" if drift_ms < 120 else "DRIFTING"
        """
        drift_ms = int(random.triangular(5, 220, 45))
        status = "OK" if drift_ms < 120 else "DRIFTING"
        
        market_open, session_msg = self.is_etoro_uk_market_open()
        now_utc = datetime.now(timezone.utc)

        return SyncDriftOutput(
            drift_ms=drift_ms,
            status=status,
            market_open=market_open,
            exchange_time=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            timestamp=now_utc.isoformat()
        )
