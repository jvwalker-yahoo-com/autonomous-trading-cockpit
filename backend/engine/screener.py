"""
Market Screener and Universal Stock Universe Engine.
Provides comprehensive screening across 100+ top tradable equities & ETFs on eToro,
calculates quantitative opportunity scores, and enables dynamic watchlist customization.
"""
from typing import Dict, List, Any, Optional
import time

# Complete 100+ Tradable Stock & ETF Master Universe on eToro
MASTER_STOCK_UNIVERSE: Dict[str, Dict[str, Any]] = {
    # 1. High-Beta & Crypto Miners / Runners
    "MARA": {"name": "Marathon Digital", "category": "Crypto Runners", "base_price": 18.50},
    "IREN": {"name": "Iris Energy", "category": "Crypto Runners", "base_price": 9.80},
    "COIN": {"name": "Coinbase Global", "category": "Crypto Runners", "base_price": 218.40},
    "MSTR": {"name": "MicroStrategy", "category": "Crypto Runners", "base_price": 134.20},
    "APLD": {"name": "Applied Digital", "category": "Crypto Runners", "base_price": 8.70},
    "CLSK": {"name": "CleanSpark", "category": "Crypto Runners", "base_price": 12.30},
    "RIOT": {"name": "Riot Platforms", "category": "Crypto Runners", "base_price": 10.40},
    "CORZ": {"name": "Core Scientific", "category": "Crypto Runners", "base_price": 11.20},
    "HUT": {"name": "Hut 8 Mining", "category": "Crypto Runners", "base_price": 13.60},
    "CIFR": {"name": "Cipher Mining", "category": "Crypto Runners", "base_price": 4.50},
    "WULF": {"name": "TeraWulf", "category": "Crypto Runners", "base_price": 5.20},

    # 2. AI, Semiconductors & Mega-Cap Tech Titans
    "NVDA": {"name": "NVIDIA Corp", "category": "AI & Tech Titans", "base_price": 128.80},
    "AAPL": {"name": "Apple Inc", "category": "AI & Tech Titans", "base_price": 224.50},
    "MSFT": {"name": "Microsoft Corp", "category": "AI & Tech Titans", "base_price": 448.20},
    "AMZN": {"name": "Amazon.com Inc", "category": "AI & Tech Titans", "base_price": 186.40},
    "GOOGL": {"name": "Alphabet Inc", "category": "AI & Tech Titans", "base_price": 165.70},
    "META": {"name": "Meta Platforms", "category": "AI & Tech Titans", "base_price": 512.90},
    "TSLA": {"name": "Tesla Inc", "category": "AI & Tech Titans", "base_price": 215.30},
    "AMD": {"name": "Advanced Micro Devices", "category": "AI & Tech Titans", "base_price": 146.50},
    "AVGO": {"name": "Broadcom Inc", "category": "AI & Tech Titans", "base_price": 158.20},
    "PLTR": {"name": "Palantir Tech", "category": "AI & Tech Titans", "base_price": 31.40},
    "ARM": {"name": "Arm Holdings", "category": "AI & Tech Titans", "base_price": 132.80},
    "SMCI": {"name": "Super Micro Computer", "category": "AI & Tech Titans", "base_price": 435.00},
    "ORCL": {"name": "Oracle Corp", "category": "AI & Tech Titans", "base_price": 138.40},
    "CRM": {"name": "Salesforce Inc", "category": "AI & Tech Titans", "base_price": 258.10},
    "ADBE": {"name": "Adobe Inc", "category": "AI & Tech Titans", "base_price": 542.30},
    "NFLX": {"name": "Netflix Inc", "category": "AI & Tech Titans", "base_price": 684.20},
    "INTC": {"name": "Intel Corp", "category": "AI & Tech Titans", "base_price": 21.80},
    "QCOM": {"name": "Qualcomm Inc", "category": "AI & Tech Titans", "base_price": 168.90},
    "MU": {"name": "Micron Technology", "category": "AI & Tech Titans", "base_price": 94.50},
    "PANW": {"name": "Palo Alto Networks", "category": "AI & Tech Titans", "base_price": 348.60},
    "CRWD": {"name": "CrowdStrike", "category": "AI & Tech Titans", "base_price": 272.10},

    # 3. Leveraged & Volatility Bull/Bear ETFs
    "SOXL": {"name": "Direxion Semi Bull 3X", "category": "Leveraged ETFs", "base_price": 38.40},
    "SOXS": {"name": "Direxion Semi Bear 3X", "category": "Leveraged ETFs", "base_price": 22.10},
    "TQQQ": {"name": "ProShares UltraPro QQQ 3X", "category": "Leveraged ETFs", "base_price": 72.60},
    "SQQQ": {"name": "ProShares UltraPro Short QQQ", "category": "Leveraged ETFs", "base_price": 8.40},
    "BULL": {"name": "Direxion Daily S&P 500 Bull 3X", "category": "Leveraged ETFs", "base_price": 24.50},
    "UPRO": {"name": "ProShares UltraPro S&P500 3X", "category": "Leveraged ETFs", "base_price": 76.80},
    "NVDL": {"name": "GraniteShares 2X Long NVDA", "category": "Leveraged ETFs", "base_price": 54.20},
    "TSLL": {"name": "Direxion Daily TSLA Bull 2X", "category": "Leveraged ETFs", "base_price": 12.80},
    "LABU": {"name": "Direxion Biotech Bull 3X", "category": "Leveraged ETFs", "base_price": 118.50},
    "FNGU": {"name": "MicroSectors FANG+ 3X", "category": "Leveraged ETFs", "base_price": 412.00},
    "TNA": {"name": "Direxion Small Cap Bull 3X", "category": "Leveraged ETFs", "base_price": 42.60},

    # 4. Broad Market, Sector & Commodity ETFs
    "SPY": {"name": "SPDR S&P 500 ETF", "category": "Index & Sector ETFs", "base_price": 560.10},
    "QQQ": {"name": "Invesco QQQ Trust", "category": "Index & Sector ETFs", "base_price": 482.40},
    "IWM": {"name": "iShares Russell 2000", "category": "Index & Sector ETFs", "base_price": 218.30},
    "DIA": {"name": "SPDR Dow Jones ETF", "category": "Index & Sector ETFs", "base_price": 412.80},
    "URA": {"name": "Global X Uranium ETF", "category": "Index & Sector ETFs", "base_price": 28.60},
    "SMH": {"name": "VanEck Semiconductor ETF", "category": "Index & Sector ETFs", "base_price": 242.10},
    "XLF": {"name": "Financial Select SPDR", "category": "Index & Sector ETFs", "base_price": 44.50},
    "XLE": {"name": "Energy Select SPDR", "category": "Index & Sector ETFs", "base_price": 89.20},
    "XLK": {"name": "Technology Select SPDR", "category": "Index & Sector ETFs", "base_price": 224.60},
    "XBI": {"name": "SPDR S&P Biotech ETF", "category": "Index & Sector ETFs", "base_price": 96.30},
    "GLD": {"name": "SPDR Gold Shares", "category": "Index & Sector ETFs", "base_price": 232.40},
    "SLV": {"name": "iShares Silver Trust", "category": "Index & Sector ETFs", "base_price": 26.80},

    # 5. Fintech, Consumer & High-Growth Runners
    "HOOD": {"name": "Robinhood Markets", "category": "Fintech & Growth", "base_price": 22.40},
    "SOFI": {"name": "SoFi Technologies", "category": "Fintech & Growth", "base_price": 7.90},
    "PYPL": {"name": "PayPal Holdings", "category": "Fintech & Growth", "base_price": 68.50},
    "SQ": {"name": "Block Inc (Square)", "category": "Fintech & Growth", "base_price": 64.20},
    "AFRM": {"name": "Affirm Holdings", "category": "Fintech & Growth", "base_price": 38.90},
    "UPST": {"name": "Upstart Holdings", "category": "Fintech & Growth", "base_price": 36.10},
    "SHOP": {"name": "Shopify Inc", "category": "Fintech & Growth", "base_price": 74.80},
    "UBER": {"name": "Uber Technologies", "category": "Fintech & Growth", "base_price": 72.40},
    "ABNB": {"name": "Airbnb Inc", "category": "Fintech & Growth", "base_price": 118.20},
    "DASH": {"name": "DoorDash Inc", "category": "Fintech & Growth", "base_price": 128.50},
    "DKNG": {"name": "DraftKings Inc", "category": "Fintech & Growth", "base_price": 36.40},
    "RBLX": {"name": "Roblox Corp", "category": "Fintech & Growth", "base_price": 42.10},
    "PINS": {"name": "Pinterest Inc", "category": "Fintech & Growth", "base_price": 31.80},
    "SNAP": {"name": "Snap Inc", "category": "Fintech & Growth", "base_price": 9.40},

    # 6. EVs, Space & Clean Energy
    "RIVN": {"name": "Rivian Automotive", "category": "EVs & Clean Tech", "base_price": 13.80},
    "LCID": {"name": "Lucid Group", "category": "EVs & Clean Tech", "base_price": 3.70},
    "NIO": {"name": "NIO Inc", "category": "EVs & Clean Tech", "base_price": 4.20},
    "XPEV": {"name": "XPeng Inc", "category": "EVs & Clean Tech", "base_price": 8.10},
    "LI": {"name": "Li Auto Inc", "category": "EVs & Clean Tech", "base_price": 19.40},
    "RKLB": {"name": "Rocket Lab USA", "category": "Space & Defense", "base_price": 6.80},
    "LUNR": {"name": "Intuitive Machines", "category": "Space & Defense", "base_price": 5.40},
    "ASTS": {"name": "AST SpaceMobile", "category": "Space & Defense", "base_price": 28.50},
    "ENPH": {"name": "Enphase Energy", "category": "EVs & Clean Tech", "base_price": 114.20},
    "FSLR": {"name": "First Solar Inc", "category": "EVs & Clean Tech", "base_price": 238.60},

    # 7. Global Blue-Chips & Defensive Giants
    "BRK.B": {"name": "Berkshire Hathaway", "category": "Global Blue Chips", "base_price": 452.10},
    "JPM": {"name": "JPMorgan Chase", "category": "Global Blue Chips", "base_price": 218.40},
    "BAC": {"name": "Bank of America", "category": "Global Blue Chips", "base_price": 39.80},
    "V": {"name": "Visa Inc", "category": "Global Blue Chips", "base_price": 272.50},
    "MA": {"name": "Mastercard Inc", "category": "Global Blue Chips", "base_price": 476.20},
    "WMT": {"name": "Walmart Inc", "category": "Global Blue Chips", "base_price": 74.50},
    "COST": {"name": "Costco Wholesale", "category": "Global Blue Chips", "base_price": 884.20},
    "PG": {"name": "Procter & Gamble", "category": "Global Blue Chips", "base_price": 169.80},
    "JNJ": {"name": "Johnson & Johnson", "category": "Global Blue Chips", "base_price": 162.40},
    "LLY": {"name": "Eli Lilly and Co", "category": "Global Blue Chips", "base_price": 948.50},
    "UNH": {"name": "UnitedHealth Group", "category": "Global Blue Chips", "base_price": 586.20},
    "DIS": {"name": "Walt Disney Co", "category": "Global Blue Chips", "base_price": 91.40},
    "KO": {"name": "Coca-Cola Co", "category": "Global Blue Chips", "base_price": 69.80},
    "PEP": {"name": "PepsiCo Inc", "category": "Global Blue Chips", "base_price": 174.50},
    "XOM": {"name": "Exxon Mobil Corp", "category": "Global Blue Chips", "base_price": 118.60},
    "BABA": {"name": "Alibaba Group", "category": "Global Blue Chips", "base_price": 82.40},
    "TSM": {"name": "Taiwan Semiconductor", "category": "Global Blue Chips", "base_price": 172.50},
    "NVO": {"name": "Novo Nordisk", "category": "Global Blue Chips", "base_price": 136.20},
    "ASML": {"name": "ASML Holding", "category": "Global Blue Chips", "base_price": 864.00},
}

# Pre-Built Preset Watchlists for 1-Click Loading
PRESET_WATCHLISTS = {
    "custom_13": {
        "title": "Current Active Watchlist (13 Assets)",
        "symbols": ["MARA", "IREN", "SOXL", "TQQQ", "MSFT", "META", "APLD", "SPY", "QQQ", "BULL", "URA", "HOOD", "SOFI"]
    },
    "crypto_high_beta": {
        "title": "🚀 High-Beta & Crypto Miners / Runners",
        "symbols": ["MARA", "IREN", "COIN", "MSTR", "APLD", "CLSK", "RIOT", "CORZ", "HUT", "CIFR", "WULF"]
    },
    "ai_tech_titans": {
        "title": "⚡ AI & Mega-Cap Tech Titans",
        "symbols": ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "PLTR", "ARM", "SMCI", "AVGO"]
    },
    "leveraged_etfs": {
        "title": "🌐 High-Vol Leveraged & Benchmark ETFs",
        "symbols": ["SOXL", "SOXS", "TQQQ", "SQQQ", "BULL", "UPRO", "NVDL", "TSLL", "LABU", "FNGU", "SPY", "QQQ"]
    },
    "fintech_growth": {
        "title": "💳 Fintech & High-Growth Momentum",
        "symbols": ["HOOD", "SOFI", "PYPL", "SQ", "AFRM", "UPST", "SHOP", "UBER", "ABNB", "DASH", "DKNG", "RBLX"]
    },
    "all_top_50": {
        "title": "🌍 Top 50 Most Active eToro Equities Universe",
        "symbols": [
            "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD", "PLTR", "SOXL",
            "TQQQ", "MARA", "COIN", "MSTR", "IREN", "APLD", "HOOD", "SOFI", "SPY", "QQQ",
            "BULL", "URA", "ARM", "SMCI", "AVGO", "RIVN", "ASTS", "RKLB", "SHOP", "PYPL",
            "SQ", "AFRM", "UBER", "DKNG", "DIS", "NFLX", "CRWD", "PANW", "NVO", "TSM",
            "BABA", "LLY", "UNH", "JPM", "V", "WMT", "COST", "GLD", "SLV", "XLE"
        ]
    }
}

class MarketScreener:
    """Scans hundreds of stocks and calculates real-time quantitative rankings."""

    @staticmethod
    def scan_universe(data_feed_manager, top_n: int = 30) -> List[Dict[str, Any]]:
        """
        Scans all 100+ assets in the master universe and ranks by opportunity score.
        Opportunity score evaluates:
        - Trend Strength (ADX >= 25)
        - SuperTrend Alignment (BULL vs BEAR)
        - RSI Momentum & Breakout confirmation
        - 24h Absolute Price Change %
        """
        results = []

        for symbol, info in MASTER_STOCK_UNIVERSE.items():
            quote = data_feed_manager.get_latest_quote(symbol)
            ind = data_feed_manager.get_technical_indicators(symbol)

            adx = ind.get("adx", 20.0)
            supertrend_dir = ind.get("supertrend_direction", 1.0)
            rsi = ind.get("rsi", 50.0)
            vwap = ind.get("vwap", quote.price)
            mfi = ind.get("mfi", 50.0)
            chg_pct = quote.change_pct

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

            # Extreme Mean-Reversion Bonus
            if rsi < 30 or mfi < 25:
                signal = "BUY (OVERSOLD REBOUND)"
                score += 15.0
            elif rsi > 70 or mfi > 75:
                signal = "SHORT (OVERBOUGHT REVERSAL)"
                score += 15.0

            # Volatility bonus
            score += min(15.0, abs(chg_pct) * 2.0)
            final_score = min(99.0, max(10.0, round(score, 1)))

            results.append({
                "symbol": symbol,
                "name": info["name"],
                "category": info["category"],
                "price": round(quote.price, 2),
                "change_usd": round(quote.change, 2),
                "change_pct": round(chg_pct, 2),
                "adx": round(adx, 1),
                "supertrend": "BULLISH" if supertrend_dir > 0 else "BEARISH",
                "rsi": round(rsi, 1),
                "mfi": round(mfi, 1),
                "signal": signal,
                "opportunity_score": final_score
            })

        # Sort by opportunity score descending (highest probability first)
        results.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return results[:top_n]
