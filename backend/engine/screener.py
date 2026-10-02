"""
Market Screener and Multi-Asset Master Universe Engine.
Provides comprehensive screening across Cryptocurrencies (24/7), ETFs, Commodities,
Indices, and Equities on eToro with quantitative opportunity scores and dynamic watchlist management.
"""
from typing import Dict, List, Any, Optional
import time
import logging
import requests

logger = logging.getLogger("auton-cockpit.screener")

# Complete Multi-Asset Master Universe on eToro (Crypto, ETFs, Commodities, Indices, Stocks)
MASTER_STOCK_UNIVERSE: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # 1. CRYPTOCURRENCIES (24/7 Continuous Trading)
    # =========================================================================
    "BTC": {"name": "Bitcoin", "category": "Crypto", "base_price": 64200.00, "asset_class": "Crypto", "trading_hours": "24/7"},
    "ETH": {"name": "Ethereum", "category": "Crypto", "base_price": 2540.00, "asset_class": "Crypto", "trading_hours": "24/7"},
    "SOL": {"name": "Solana", "category": "Crypto", "base_price": 142.50, "asset_class": "Crypto", "trading_hours": "24/7"},
    "XRP": {"name": "XRP (Ripple)", "category": "Crypto", "base_price": 0.58, "asset_class": "Crypto", "trading_hours": "24/7"},
    "BNB": {"name": "Binance Coin", "category": "Crypto", "base_price": 565.00, "asset_class": "Crypto", "trading_hours": "24/7"},
    "DOGE": {"name": "Dogecoin", "category": "Crypto", "base_price": 0.11, "asset_class": "Crypto", "trading_hours": "24/7"},
    "ADA": {"name": "Cardano", "category": "Crypto", "base_price": 0.36, "asset_class": "Crypto", "trading_hours": "24/7"},
    "AVAX": {"name": "Avalanche", "category": "Crypto", "base_price": 24.80, "asset_class": "Crypto", "trading_hours": "24/7"},
    "LINK": {"name": "Chainlink", "category": "Crypto", "base_price": 11.90, "asset_class": "Crypto", "trading_hours": "24/7"},
    "DOT": {"name": "Polkadot", "category": "Crypto", "base_price": 4.40, "asset_class": "Crypto", "trading_hours": "24/7"},
    "NEAR": {"name": "NEAR Protocol", "category": "Crypto", "base_price": 4.80, "asset_class": "Crypto", "trading_hours": "24/7"},
    "MATIC": {"name": "Polygon", "category": "Crypto", "base_price": 0.42, "asset_class": "Crypto", "trading_hours": "24/7"},
    "SHIB": {"name": "Shiba Inu", "category": "Crypto", "base_price": 0.000015, "asset_class": "Crypto", "trading_hours": "24/7"},
    "LTC": {"name": "Litecoin", "category": "Crypto", "base_price": 66.20, "asset_class": "Crypto", "trading_hours": "24/7"},
    "UNI": {"name": "Uniswap", "category": "Crypto", "base_price": 6.80, "asset_class": "Crypto", "trading_hours": "24/7"},
    "RENDER": {"name": "Render Token", "category": "Crypto", "base_price": 5.90, "asset_class": "Crypto", "trading_hours": "24/7"},
    "FET": {"name": "Artificial Superintelligence", "category": "Crypto", "base_price": 1.35, "asset_class": "Crypto", "trading_hours": "24/7"},
    "SUI": {"name": "Sui", "category": "Crypto", "base_price": 0.92, "asset_class": "Crypto", "trading_hours": "24/7"},
    "PEPE": {"name": "Pepe", "category": "Crypto", "base_price": 0.000008, "asset_class": "Crypto", "trading_hours": "24/7"},

    # =========================================================================
    # 2. COMMODITIES (Metals, Energy, Softs & Agriculture)
    # =========================================================================
    "GOLD": {"name": "Gold (Spot Non-Expiry)", "category": "Commodities", "base_price": 2510.00, "asset_class": "Commodity", "trading_hours": "24/7 (Break 22:00-23:00)"},
    "SILVER": {"name": "Silver (Spot Non-Expiry)", "category": "Commodities", "base_price": 29.40, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "OIL": {"name": "Crude Oil (Brent/WTI)", "category": "Commodities", "base_price": 74.50, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "NATGAS": {"name": "Natural Gas", "category": "Commodities", "base_price": 2.25, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "COPPER": {"name": "Copper (Non-Expiry)", "category": "Commodities", "base_price": 4.22, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "PLATINUM": {"name": "Platinum", "category": "Commodities", "base_price": 945.00, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "PALLADIUM": {"name": "Palladium", "category": "Commodities", "base_price": 980.00, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "GASOLINE": {"name": "RBOB Gasoline", "category": "Commodities", "base_price": 2.18, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "SUGAR": {"name": "Sugar", "category": "Commodities", "base_price": 19.40, "asset_class": "Commodity", "trading_hours": "Mon 08:30 - Fri 18:00 UK"},
    "COTTON": {"name": "Cotton", "category": "Commodities", "base_price": 72.50, "asset_class": "Commodity", "trading_hours": "Mon 02:00 - Fri 19:20 UK"},
    "COCOA": {"name": "Cocoa", "category": "Commodities", "base_price": 7850.00, "asset_class": "Commodity", "trading_hours": "Mon 09:45 - Fri 18:30 UK"},
    "COFFEE": {"name": "Coffee", "category": "Commodities", "base_price": 245.00, "asset_class": "Commodity", "trading_hours": "Mon 09:15 - Fri 18:30 UK"},
    "WHEAT": {"name": "Wheat", "category": "Commodities", "base_price": 545.00, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "CORN": {"name": "Corn", "category": "Commodities", "base_price": 405.00, "asset_class": "Commodity", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},

    # =========================================================================
    # 3. GLOBAL BENCHMARK INDICES
    # =========================================================================
    "SPX500": {"name": "S&P 500 Index", "category": "Indices", "base_price": 5610.00, "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "NSDQ100": {"name": "Nasdaq 100 Index", "category": "Indices", "base_price": 19650.00, "asset_class": "Index", "trading_hours": "24/7 (Break 22:00-23:00)"},
    "DJ30": {"name": "Dow Jones 30", "category": "Indices", "base_price": 41500.00, "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "RUSSELL2000": {"name": "Russell 2000 Index", "category": "Indices", "base_price": 2210.00, "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "USDOLLAR": {"name": "US Dollar Index (DXY)", "category": "Indices", "base_price": 101.50, "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "VIX": {"name": "CBOE Volatility Index", "category": "Indices", "base_price": 15.80, "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "UK100": {"name": "FTSE 100 (UK)", "category": "Indices", "base_price": 8380.00, "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    "GER40": {"name": "DAX 40 (Germany)", "category": "Indices", "base_price": 18850.00, "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    "FRA40": {"name": "CAC 40 (France)", "category": "Indices", "base_price": 7620.00, "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    "ESP35": {"name": "IBEX 35 (Spain)", "category": "Indices", "base_price": 11350.00, "asset_class": "Index", "trading_hours": "Mon 08:00 - Fri 16:30 UK"},
    "JPN225": {"name": "Nikkei 225 (Japan)", "category": "Indices", "base_price": 38650.00, "asset_class": "Index", "trading_hours": "Sun 23:00 - Fri 21:30 UK"},
    "HKG50": {"name": "Hang Seng (Hong Kong)", "category": "Indices", "base_price": 17700.00, "asset_class": "Index", "trading_hours": "Mon 01:15 - Fri 08:00 UK"},
    "AUS200": {"name": "ASX 200 (Australia)", "category": "Indices", "base_price": 8100.00, "asset_class": "Index", "trading_hours": "Mon 01:00 - Fri 07:00 UK"},

    # =========================================================================
    # 4. BENCHMARK, THEMATIC & LEVERAGED ETFS
    # =========================================================================
    "SPY": {"name": "SPDR S&P 500 ETF", "category": "ETFs", "base_price": 560.10, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "QQQ": {"name": "Invesco QQQ Trust", "category": "ETFs", "base_price": 482.40, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "IWM": {"name": "iShares Russell 2000", "category": "ETFs", "base_price": 218.30, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "DIA": {"name": "SPDR Dow Jones Industrial", "category": "ETFs", "base_price": 412.80, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "VOO": {"name": "Vanguard S&P 500 ETF", "category": "ETFs", "base_price": 514.20, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "VTI": {"name": "Vanguard Total Stock Market", "category": "ETFs", "base_price": 274.60, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "SOXL": {"name": "Direxion Semi Bull 3X", "category": "Leveraged ETFs", "base_price": 38.40, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "SOXS": {"name": "Direxion Semi Bear 3X", "category": "Leveraged ETFs", "base_price": 22.10, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "TQQQ": {"name": "ProShares UltraPro QQQ 3X", "category": "Leveraged ETFs", "base_price": 72.60, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "SQQQ": {"name": "ProShares UltraPro Short QQQ", "category": "Leveraged ETFs", "base_price": 8.40, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "BULL": {"name": "Direxion S&P 500 Bull 3X", "category": "Leveraged ETFs", "base_price": 24.50, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "UPRO": {"name": "ProShares UltraPro S&P500 3X", "category": "Leveraged ETFs", "base_price": 76.80, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "NVDL": {"name": "GraniteShares 2X Long NVDA", "category": "Leveraged ETFs", "base_price": 54.20, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "TSLL": {"name": "Direxion Daily TSLA Bull 2X", "category": "Leveraged ETFs", "base_price": 12.80, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "LABU": {"name": "Direxion Biotech Bull 3X", "category": "Leveraged ETFs", "base_price": 118.50, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "FNGU": {"name": "MicroSectors FANG+ 3X", "category": "Leveraged ETFs", "base_price": 412.00, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "SMH": {"name": "VanEck Semiconductor ETF", "category": "ETFs", "base_price": 242.10, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "XLK": {"name": "Technology Select SPDR", "category": "ETFs", "base_price": 224.60, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "XLF": {"name": "Financial Select SPDR", "category": "ETFs", "base_price": 44.50, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "XLE": {"name": "Energy Select SPDR", "category": "ETFs", "base_price": 89.20, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "XLV": {"name": "Health Care Select SPDR", "category": "ETFs", "base_price": 152.40, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "XLI": {"name": "Industrial Select SPDR", "category": "ETFs", "base_price": 128.90, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "XBI": {"name": "SPDR S&P Biotech ETF", "category": "ETFs", "base_price": 96.30, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "URA": {"name": "Global X Uranium ETF", "category": "ETFs", "base_price": 28.60, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "ARKK": {"name": "ARK Innovation ETF", "category": "ETFs", "base_price": 46.80, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "GDX": {"name": "VanEck Gold Miners ETF", "category": "ETFs", "base_price": 38.90, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "TAN": {"name": "Invesco Solar ETF", "category": "ETFs", "base_price": 41.20, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},
    "TLT": {"name": "iShares 20+ Year Treasury", "category": "ETFs", "base_price": 98.40, "asset_class": "ETF", "trading_hours": "14:30 - 21:00 UK"},

    # =========================================================================
    # 5. HIGH-GROWTH & MEGA-CAP EQUITIES
    # =========================================================================
    "NVDA": {"name": "NVIDIA Corp", "category": "AI & Tech Titans", "base_price": 128.80, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "AAPL": {"name": "Apple Inc", "category": "AI & Tech Titans", "base_price": 224.50, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "MSFT": {"name": "Microsoft Corp", "category": "AI & Tech Titans", "base_price": 448.20, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "AMZN": {"name": "Amazon.com Inc", "category": "AI & Tech Titans", "base_price": 186.40, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "GOOGL": {"name": "Alphabet Inc", "category": "AI & Tech Titans", "base_price": 165.70, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "META": {"name": "Meta Platforms", "category": "AI & Tech Titans", "base_price": 512.90, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "TSLA": {"name": "Tesla Inc", "category": "AI & Tech Titans", "base_price": 215.30, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "AMD": {"name": "Advanced Micro Devices", "category": "AI & Tech Titans", "base_price": 146.50, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "AVGO": {"name": "Broadcom Inc", "category": "AI & Tech Titans", "base_price": 158.20, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "PLTR": {"name": "Palantir Tech", "category": "AI & Tech Titans", "base_price": 31.40, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "ARM": {"name": "Arm Holdings", "category": "AI & Tech Titans", "base_price": 132.80, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "SMCI": {"name": "Super Micro Computer", "category": "AI & Tech Titans", "base_price": 435.00, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "MARA": {"name": "Marathon Digital", "category": "Crypto Runners", "base_price": 18.50, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "IREN": {"name": "Iris Energy", "category": "Crypto Runners", "base_price": 9.80, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "COIN": {"name": "Coinbase Global", "category": "Crypto Runners", "base_price": 218.40, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "MSTR": {"name": "MicroStrategy", "category": "Crypto Runners", "base_price": 134.20, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "APLD": {"name": "Applied Digital", "category": "Crypto Runners", "base_price": 8.70, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "HOOD": {"name": "Robinhood Markets", "category": "Fintech & Growth", "base_price": 22.40, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "SOFI": {"name": "SoFi Technologies", "category": "Fintech & Growth", "base_price": 7.90, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "RIVN": {"name": "Rivian Automotive", "category": "EVs & Clean Tech", "base_price": 13.80, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "ASTS": {"name": "AST SpaceMobile", "category": "Space & Defense", "base_price": 28.50, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "RKLB": {"name": "Rocket Lab USA", "category": "Space & Defense", "base_price": 6.80, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "BABA": {"name": "Alibaba Group", "category": "Global Blue Chips", "base_price": 82.40, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "TSM": {"name": "Taiwan Semiconductor", "category": "Global Blue Chips", "base_price": 172.50, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"},
    "LLY": {"name": "Eli Lilly and Co", "category": "Global Blue Chips", "base_price": 948.50, "asset_class": "Stock", "trading_hours": "14:30 - 21:00 UK"}
}

# Pre-Built Preset Watchlists for 1-Click Multi-Asset Loading
PRESET_WATCHLISTS = {
    "commodities_metals_energy": {
        "title": "🛢️ Commodities (Gold, Silver, Oil, NatGas, Copper)",
        "symbols": ["GOLD", "SILVER", "OIL", "NATGAS", "COPPER", "PLATINUM", "PALLADIUM", "GASOLINE", "SUGAR", "COCOA", "COFFEE", "CORN", "WHEAT", "COTTON"]
    },
    "global_indices": {
        "title": "📈 Global Benchmark Indices (SPX, Nasdaq, Dow, FTSE, DAX, Nikkei)",
        "symbols": ["SPX500", "NSDQ100", "DJ30", "RUSSELL2000", "USDOLLAR", "VIX", "UK100", "GER40", "FRA40", "JPN225", "HKG50", "AUS200"]
    },
    "top_etfs": {
        "title": "🌐 Top Benchmark & Leveraged ETFs",
        "symbols": ["SPY", "QQQ", "IWM", "DIA", "SOXL", "SOXS", "TQQQ", "SQQQ", "BULL", "UPRO", "SMH", "XLK", "XLE", "URA", "TLT"]
    },
    "ai_tech_titans": {
        "title": "⚡ AI & Mega-Cap Tech Titans",
        "symbols": ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "PLTR", "ARM", "SMCI", "AVGO"]
    },
    "multi_asset_macro": {
        "title": "🌍 Multi-Asset Macro Universe (Commodities + Indices + ETFs + Stocks)",
        "symbols": [
            "GOLD", "OIL", "SILVER", "NATGAS", "SPX500", "NSDQ100", "DJ30",
            "UK100", "GER40", "JPN225", "SPY", "QQQ", "SOXL", "TQQQ", "NVDA", "TSLA", "AAPL",
            "MSFT", "META", "PLTR", "MARA", "COIN", "MSTR", "HOOD", "URA", "SMCI", "RKLB"
        ]
    },
    "custom_13": {
        "title": "🎯 Classic Default Watchlist (13 Assets)",
        "symbols": ["MARA", "IREN", "SOXL", "TQQQ", "MSFT", "META", "APLD", "SPY", "QQQ", "BULL", "URA", "HOOD", "SOFI"]
    },
    "day_trade_movers": {
        "title": "⚡ Day Trading Movers (High-Beta Intraday Runners)",
        "symbols": ["NVDA", "TSLA", "PLTR", "ARM", "SMCI", "AMD", "META", "MSFT", "HOOD", "MARA", "COIN", "IREN", "MSTR"]
    }
}

PROHIBITED_CRYPTO = {
    "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LINK", "DOT", "NEAR", "MATIC",
    "SHIB", "LTC", "UNI", "RENDER", "FET", "SUI", "PEPE", "ALGO", "ATOM", "FTM"
}

# Assets with structural execution restrictions on eToro UK retail accounts:
# 1. Commodities require $1,000 minimum exposure on eToro and buy is restricted.
# 2. US-domiciled ETFs are restricted by UK PRIIPs regulations.
UNTRADABLE_RETAIL_SYMBOLS = {
    "GOLD", "SILVER", "OIL", "NATGAS", "COPPER", "PLATINUM", "PALLADIUM",
    "GASOLINE", "SUGAR", "COTTON", "COCOA", "COFFEE", "WHEAT", "CORN",
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "SOXL", "SOXS", "TQQQ",
    "SQQQ", "BULL", "UPRO", "NVDL", "TSLL", "LABU", "FNGU", "SMH",
    "XLK", "XLF", "XLE", "XLV", "XLI", "XBI", "URA", "ARKK", "GDX", "TAN", "TLT"
}

class MarketScreener:
    """Scans all multi-asset instruments across Commodities, Indices, ETFs, and Equities (Crypto Deactivated)."""

    @staticmethod
    def scan_universe(
        data_feed_manager=None,
        category_filter: Optional[str] = None,
        top_n: int = 35,
        tradable_only: bool = False,
        day_trade_only: bool = False,
        smart_money_engine=None
    ) -> List[Dict[str, Any]]:
        """
        Scans multi-asset instruments and ranks by quantitative opportunity score.
        Evaluates:
        - Trend Strength (ADX >= 25)
        - SuperTrend Alignment (BULL vs BEAR)
        - RSI Momentum & Breakout confirmation
        - Pattern Recognition (Double Bottom, Double Top, Range Breakout)
        - Volume Surge Factor (Ratio > 1.2)
        - 24h Absolute Price Change %
        """
        if data_feed_manager is None:
            from .data_feed import DataFeedManager
            data_feed_manager = DataFeedManager()

        results = []

        for symbol, info in MASTER_STOCK_UNIVERSE.items():
            # Permanent exclusion of Crypto per user mandate
            if symbol in PROHIBITED_CRYPTO or info.get("category", "").lower() == "crypto" or info.get("asset_class", "").lower() == "crypto":
                continue

            # When screening for autonomous trading, exclude commodities ($1,000 margin) and PRIIPs ETFs
            if tradable_only or day_trade_only or (category_filter and category_filter.lower() in ("stock", "daytrade", "day_trade")):
                if symbol in UNTRADABLE_RETAIL_SYMBOLS or info.get("asset_class", "").lower() != "stock":
                    continue

            if category_filter and category_filter.lower() not in ("all", "stock", "daytrade", "day_trade"):
                if info.get("category", "").lower() != category_filter.lower() and info.get("asset_class", "").lower() != category_filter.lower():
                    continue

            quote = data_feed_manager.get_latest_quote(symbol)
            ind = data_feed_manager.get_technical_indicators(symbol)

            adx = ind.get("adx", 20.0)
            supertrend_dir = ind.get("supertrend_direction", ind.get("supertrend_dir", 1.0))
            rsi = ind.get("rsi_14", ind.get("rsi", 50.0))
            vwap = ind.get("vwap", quote.price)
            mfi = ind.get("mfi", 50.0)
            chg_pct = quote.change_pct
            vol_surge = ind.get("volume_surge", 1.0)
            breakout = ind.get("breakout_type", "NONE")
            db_det = ind.get("double_bottom_detected", 0.0) > 0
            dt_det = ind.get("double_top_detected", 0.0) > 0

            # Calculate Quantitative Score (0 to 100)
            score = 50.0
            
            # Trend strength bonus (high ADX indicates strong directional move)
            if adx >= 30:
                score += 20.0
            elif adx >= 22:
                score += 10.0

            # Momentum / SuperTrend direction
            if supertrend_dir > 0: # BULL
                signal = "BUY"
                if quote.price > vwap:
                    score += 15.0
                if rsi > 50 and rsi < 70:
                    score += 10.0
            else: # BEAR
                signal = "SHORT"
                if quote.price < vwap:
                    score += 15.0
                if rsi < 50 and rsi > 30:
                    score += 10.0

            # Pattern recognition bonuses
            if db_det:
                signal = "BUY (DOUBLE BOTTOM)"
                score += 16.0
            elif dt_det:
                signal = "SHORT (DOUBLE TOP)"
                score += 16.0

            if breakout == "BULL_BREAKOUT":
                signal = "BUY (RANGE BREAKOUT)"
                score += 14.0
            elif breakout == "BEAR_BREAKDOWN":
                signal = "SHORT (RANGE BREAKDOWN)"
                score += 14.0

            # Volume surge confirmation bonus
            if vol_surge >= 1.5:
                score += 12.0
            elif vol_surge >= 1.2:
                score += 6.0

            # Extreme Mean-Reversion Bonus
            if rsi < 30 or mfi < 25:
                signal = "BUY (OVERSOLD REBOUND)"
                score += 15.0
            elif rsi > 70 or mfi > 75:
                signal = "SHORT (OVERBOUGHT REVERSAL)"
                score += 15.0

            # Congressional / Smart Money Conviction Bonus
            congress_score = smart_money_engine.get_congress_conviction(symbol) if smart_money_engine else 0.0
            if congress_score >= 0.20:
                score += min(18.0, congress_score * 20.0)
                signal = f"{signal} + CONGRESS BUY"
            elif congress_score <= -0.25:
                score -= min(15.0, abs(congress_score) * 15.0)

            # Volatility bonus
            score += min(15.0, abs(chg_pct) * 2.0)
            final_score = min(99.0, max(10.0, round(score, 1)))

            # Horizon classification
            is_day_setup = (vol_surge >= 1.25 or breakout != "NONE" or db_det or dt_det or adx >= 26)
            rec_horizon = "DAY" if is_day_setup else "LONG-TERM"

            if (day_trade_only or (category_filter and category_filter.lower() in ("daytrade", "day_trade"))) and not is_day_setup:
                continue

            pattern_desc = "Double Bottom" if db_det else ("Double Top" if dt_det else (breakout if breakout != "NONE" else "Trend Continuation"))
            if congress_score >= 0.20:
                pattern_desc = f"{pattern_desc} [Congress Accumulation]"
            elif congress_score <= -0.25:
                pattern_desc = f"{pattern_desc} [Congress Distribution]"

            results.append({
                "symbol": symbol,
                "name": info["name"],
                "category": info["category"],
                "asset_class": info.get("asset_class", "Stock"),
                "trading_hours": info.get("trading_hours", "eToro Hours"),
                "price": round(quote.price, 4 if quote.price < 1.0 else 2),
                "change_usd": round(quote.change, 4 if abs(quote.change) < 0.1 else 2),
                "change_pct": round(chg_pct, 2),
                "adx": round(adx, 1),
                "supertrend": "BULLISH" if supertrend_dir > 0 else "BEARISH",
                "rsi": round(rsi, 1),
                "mfi": round(mfi, 1),
                "volume_surge": round(vol_surge, 1),
                "pattern": pattern_desc,
                "recommended_horizon": rec_horizon,
                "signal": signal,
                "opportunity_score": final_score,
                "congress_conviction": round(congress_score, 2)
            })

        # Sort by opportunity score descending
        results.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return results[:top_n]

    # ── TradingView Screener & Technical Consensus Engine ───────────────────
    _tv_cache: List[Dict[str, Any]] = []
    _tv_cache_time: float = 0.0
    _tv_cache_ttl: float = 300.0  # 5 minutes cache to prevent rate-limiting

    _tv_consensus_cache: Dict[str, Dict[str, Any]] = {}
    _tv_consensus_cache_time: float = 0.0
    _tv_consensus_cache_ttl: float = 180.0  # 3 minutes cache

    @classmethod
    def scan_tradingview_volume_breakouts(
        cls,
        min_rvol: float = 1.5,
        min_price: float = 5.0,
        top_n: int = 25,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scans US equities for abnormal relative volume breakouts (RVOL > 1.5x 10-day average)
        and multi-timeframe technical consensus directly from TradingView's official screener backend.
        Results are cached for 5 minutes to prevent rate-limiting.
        """
        now = time.time()
        if not force_refresh and cls._tv_cache and (now - cls._tv_cache_time < cls._tv_cache_ttl):
            return cls._tv_cache[:top_n]

        url = "https://scanner.tradingview.com/america/scan"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "filter": [
                {"left": "volume", "operation": "greater", "right": 100000},
                {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
                {"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE", "AMEX"]},
                {"left": "relative_volume_10d_calc", "operation": "greater", "right": min_rvol},
                {"left": "close", "operation": "greater", "right": min_price}
            ],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": [
                "name",
                "description",
                "close",
                "change",
                "volume",
                "relative_volume_10d_calc",
                "Recommend.All",
                "Recommend.MA",
                "Recommend.Other",
                "Recommend.All|60",
                "Recommend.All|15",
                "RSI",
                "MACD.macd",
                "MACD.signal"
            ],
            "sort": {"sortBy": "relative_volume_10d_calc", "sortOrder": "desc"},
            "range": [0, max(top_n, 30)]
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=8)
            if resp.status_code != 200:
                logger.warning(f"TradingView screener returned HTTP {resp.status_code}")
                return cls._tv_cache[:top_n]

            data = resp.json().get("data", [])
            results = []

            def _to_consensus(score: float) -> str:
                if score >= 0.5:
                    return "STRONG_BUY"
                elif score >= 0.1:
                    return "BUY"
                elif score <= -0.5:
                    return "STRONG_SELL"
                elif score <= -0.1:
                    return "SELL"
                return "NEUTRAL"

            for item in data:
                ticker = item.get("s", "")
                d = item.get("d", [])
                if len(d) >= 12:
                    sym = str(d[0]).upper()
                    # Exclude crypto or restricted symbols
                    if sym in PROHIBITED_CRYPTO:
                        continue

                    rec_1d = float(d[6] or 0.0)
                    rec_1h = float(d[9] if len(d) > 9 and d[9] is not None else rec_1d)
                    rec_15m = float(d[10] if len(d) > 10 and d[10] is not None else rec_1h)

                    rvol = round(float(d[5]), 2) if d[5] is not None else 1.0
                    price = round(float(d[2]), 2) if d[2] is not None else 0.0
                    chg = round(float(d[3]), 2) if d[3] is not None else 0.0

                    results.append({
                        "ticker": ticker,
                        "symbol": sym,
                        "name": d[1] or sym,
                        "price": price,
                        "change_pct": chg,
                        "volume": int(d[4]) if d[4] is not None else 0,
                        "relative_volume": rvol,
                        "recommend_score": round(rec_1d, 3),
                        "consensus_1d": _to_consensus(rec_1d),
                        "consensus_1h": _to_consensus(rec_1h),
                        "consensus_15m": _to_consensus(rec_15m),
                        "rsi": round(float(d[11]), 1) if len(d) > 11 and d[11] is not None else None,
                        "is_etoro_anchor": sym in MASTER_STOCK_UNIVERSE
                    })

            if results:
                cls._tv_cache = results
                cls._tv_cache_time = now

            return results[:top_n]

        except Exception as e:
            logger.warning(f"TradingView volume breakout scan error: {e}")
            return cls._tv_cache[:top_n]

    @classmethod
    def get_tradingview_technical_consensus(
        cls,
        symbols: List[str],
        force_refresh: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch-queries TradingView scanner for technical consensus on specific symbols.
        Returns multi-timeframe consensus (15m, 1h, 1D), RSI, and relative volume.
        Cached for 3 minutes.
        """
        clean_symbols = [str(s).upper() for s in symbols if str(s).upper() not in PROHIBITED_CRYPTO]
        if not clean_symbols:
            return {}

        now = time.time()
        if not force_refresh and (now - cls._tv_consensus_cache_time < cls._tv_consensus_cache_ttl):
            cached = {s: cls._tv_consensus_cache[s] for s in clean_symbols if s in cls._tv_consensus_cache}
            if len(cached) >= len(clean_symbols) * 0.8:
                return cached

        url = "https://scanner.tradingview.com/america/scan"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }

        payload = {
            "filter": [{"left": "name", "operation": "in_range", "right": clean_symbols}],
            "columns": [
                "name", "close", "change",
                "Recommend.All", "Recommend.MA", "Recommend.Other",
                "Recommend.All|60", "Recommend.All|15",
                "RSI", "relative_volume_10d_calc"
            ]
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=6)
            if resp.status_code != 200:
                return cls._tv_consensus_cache

            def _to_consensus(score: float) -> str:
                if score >= 0.5:
                    return "STRONG_BUY"
                elif score >= 0.1:
                    return "BUY"
                elif score <= -0.5:
                    return "STRONG_SELL"
                elif score <= -0.1:
                    return "SELL"
                return "NEUTRAL"

            results = dict(cls._tv_consensus_cache)
            for row in resp.json().get("data", []):
                d = row.get("d", [])
                if len(d) >= 10:
                    sym = str(d[0]).upper()
                    rec_1d = float(d[3] or 0.0)
                    rec_1h = float(d[6] if d[6] is not None else rec_1d)
                    rec_15m = float(d[7] if d[7] is not None else rec_1h)
                    results[sym] = {
                        "symbol": sym,
                        "close": round(float(d[1] or 0.0), 2),
                        "change_pct": round(float(d[2] or 0.0), 2),
                        "recommend_score_1d": round(rec_1d, 3),
                        "recommend_score_1h": round(rec_1h, 3),
                        "recommend_score_15m": round(rec_15m, 3),
                        "consensus_1d": _to_consensus(rec_1d),
                        "consensus_1h": _to_consensus(rec_1h),
                        "consensus_15m": _to_consensus(rec_15m),
                        "rsi": round(float(d[8]), 1) if d[8] is not None else None,
                        "relative_volume": round(float(d[9]), 2) if d[9] is not None else 1.0,
                        "source": "TradingView Scanner"
                    }

            cls._tv_consensus_cache = results
            cls._tv_consensus_cache_time = now
            return {s: results[s] for s in clean_symbols if s in results}

        except Exception as e:
            logger.warning(f"TradingView consensus fetch error: {e}")
            return cls._tv_consensus_cache

    @classmethod
    def scan_smart_money_opportunities(
        cls,
        smart_money_engine,
        top_n: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Cross-matches Congressional & Smart Money accumulation with TradingView volume breakouts.
        Returns high-conviction trade setups where Congress is buying AND technical momentum aligns.
        """
        candidates = smart_money_engine.get_trade_candidates()
        if not candidates:
            try:
                smart_money_engine.refresh_all()
                candidates = smart_money_engine.get_trade_candidates()
            except Exception as e:
                logger.warning(f"Smart money opportunity refresh error: {e}")

        symbols_to_check = [c["symbol"] for c in candidates if c.get("symbol")]
        tv_consensus = cls.get_tradingview_technical_consensus(symbols_to_check) if symbols_to_check else {}

        results = []
        for cand in candidates:
            sym = cand["symbol"]
            tv_data = tv_consensus.get(sym, {})
            c_1d = tv_data.get("consensus_1d", "NEUTRAL")
            c_1h = tv_data.get("consensus_1h", "NEUTRAL")
            rvol = tv_data.get("relative_volume", 1.0)
            
            # High conviction when TradingView agrees with Congressional buying
            is_confirmed = (c_1d in ("BUY", "STRONG_BUY") or c_1h in ("BUY", "STRONG_BUY"))
            
            results.append({
                "symbol": sym,
                "signal": "HIGH_CONVICTION_BUY" if is_confirmed else "CONGRESS_ACCUMULATION",
                "congress_conviction": cand["conviction_score"],
                "buyers": cand.get("buyers", []),
                "tradingview_1d": c_1d,
                "tradingview_1h": c_1h,
                "relative_volume": rvol,
                "latest_filing": cand.get("latest_filing", "Recent"),
                "is_etoro_anchor": sym in MASTER_STOCK_UNIVERSE
            })

        results.sort(key=lambda x: (x["signal"] == "HIGH_CONVICTION_BUY", x["congress_conviction"]), reverse=True)
        return results[:top_n]
