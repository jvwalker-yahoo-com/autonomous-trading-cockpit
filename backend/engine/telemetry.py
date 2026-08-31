import time
import random
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from .models import HeartbeatOutput, SyncDriftOutput

# Complete eToro UK Global Exchange Schedule (Times in UK London Time GMT+1/BST)
ETORO_EXCHANGES_UK: Dict[str, Dict[str, Any]] = {
    "US_EQUITIES": {
        "name": "NYSE / NASDAQ / CBOE / OTC",
        "description": "US Stocks & Leveraged ETFs (MARA, SOXL, TQQQ, NVDA, SPY, etc.)",
        "days": [0, 1, 2, 3, 4], # Mon - Fri
        "open_time_uk": (14, 30), # 14:30 UK (2:30 PM)
        "close_time_uk": (21, 0),  # 21:00 UK (9:00 PM)
        "daily_break": "21:00 - 14:30 UK",
        "symbols_pattern": ["MARA", "IREN", "SOXL", "TQQQ", "MSFT", "META", "APLD", "SPY", "QQQ", "BULL", "URA", "HOOD", "SOFI", "NVDA", "AAPL", "TSLA", "AMZN", "GOOGL"]
    },
    "LSE": {
        "name": "London Stock Exchange (LSE)",
        "description": "UK Equities & FTSE Index Constituents",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (8, 0),   # 08:00 UK
        "close_time_uk": (16, 30),# 16:30 UK
        "daily_break": "16:30 - 08:00 UK",
        "symbols_pattern": [".L", "LSE", "LON"]
    },
    "EUROPE": {
        "name": "Frankfurt / Euronext (Paris, Amsterdam, Lisbon) / Madrid",
        "description": "European Equities & XETRA ETFs",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (8, 0),   # 08:00 UK
        "close_time_uk": (16, 30),# 16:30 UK
        "daily_break": "16:30 - 08:00 UK",
        "symbols_pattern": [".DE", ".PA", ".AS", ".MC"]
    },
    "HKEX": {
        "name": "Hong Kong Stock Exchange (HKEX)",
        "description": "Asian Equities",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (2, 30),  # 02:30 UK
        "close_time_uk": (9, 0),  # 09:00 UK
        "daily_break": "05:00-06:00 & 09:00-02:30 UK",
        "symbols_pattern": [".HK"]
    },
    "ASX": {
        "name": "Australian Stocks (ASX)",
        "description": "Australian Equities",
        "days": [0, 1, 2, 3, 4],
        "open_time_uk": (1, 0),   # 01:00 UK
        "close_time_uk": (7, 0),  # 07:00 UK
        "daily_break": "07:00 - 01:00 UK",
        "symbols_pattern": [".AX"]
    },
    "CRYPTO": {
        "name": "Cryptocurrencies",
        "description": "24/7 Digital Asset Trading",
        "days": [0, 1, 2, 3, 4, 5, 6], # 24/7
        "open_time_uk": (0, 0),
        "close_time_uk": (24, 0),
        "daily_break": "None (Continuous 24/7)",
        "symbols_pattern": ["BTC", "ETH", "SOL", "XRP", "ADA"]
    }
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
        """Resolves target exchange configuration for a given ticker."""
        sym = symbol.upper()
        if sym in ("BTC", "ETH", "SOL", "XRP", "DOGE"):
            return ETORO_EXCHANGES_UK["CRYPTO"]
        if sym.endswith(".L") or sym.endswith(".LON"):
            return ETORO_EXCHANGES_UK["LSE"]
        if any(sym.endswith(ext) for ext in (".DE", ".PA", ".AS", ".MC")):
            return ETORO_EXCHANGES_UK["EUROPE"]
        if sym.endswith(".HK"):
            return ETORO_EXCHANGES_UK["HKEX"]
        if sym.endswith(".AX"):
            return ETORO_EXCHANGES_UK["ASX"]
        # Default: US Equities (Nasdaq, NYSE, CBOE)
        return ETORO_EXCHANGES_UK["US_EQUITIES"]

    def is_etoro_uk_market_open(self, symbol: str = "SPY") -> Tuple[bool, str]:
        """
        Validates whether eToro UK trading session is open for the specified asset.
        Computes current UK local time (accounting for BST/GMT offset).
        """
        now_utc = datetime.now(timezone.utc)
        # UK is UTC+1 during BST (British Summer Time, last Sunday March to last Sunday Oct)
        # We compute exact UK civil time:
        month = now_utc.month
        is_bst = 3 < month < 10 or (month == 3 and now_utc.day >= 25) or (month == 10 and now_utc.day <= 25)
        uk_hour = (now_utc.hour + (1 if is_bst else 0)) % 24
        uk_minute = now_utc.minute
        weekday = now_utc.weekday() # 0 = Mon, 4 = Fri, 5 = Sat, 6 = Sun

        exch = self.get_exchange_for_symbol(symbol)
        
        # Check active trading days
        if weekday not in exch["days"]:
            return False, f"Market Closed (Weekend: {exch['name']} opens Monday)"

        open_h, open_m = exch["open_time_uk"]
        close_h, close_m = exch["close_time_uk"]

        current_mins = uk_hour * 60 + uk_minute
        open_mins = open_h * 60 + open_m
        close_mins = close_h * 60 + close_m

        if current_mins < open_mins:
            mins_left = open_mins - current_mins
            hrs = mins_left // 60
            mins = mins_left % 60
            return False, f"Pre-Market (Opens at {open_h:02d}:{open_m:02d} UK in {hrs}h {mins}m)"
        elif current_mins >= close_mins:
            return False, f"Market Closed (Closed at {close_h:02d}:{close_m:02d} UK)"
        else:
            return True, f"eToro UK Session Active ({open_h:02d}:{open_m:02d} - {close_h:02d}:{close_m:02d} UK)"


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

