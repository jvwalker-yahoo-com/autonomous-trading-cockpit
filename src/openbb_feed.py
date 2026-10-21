"""OpenBB Feed Wrapper

This module provides a unified, high‑level interface to the OpenBB platform, exposing the most useful data domains for the Autonomous Trading Cockpit:

* **Macro & Economic Intelligence** – GDP, CPI, interest rates, etc.
* **Equity Fundamentals & Market Depth** – company fundamentals, order‑book depth, historical prices.
* **News** – Bloomberg‑sourced headlines and general market news.
* **Crypto** – price history and market data for cryptocurrencies.

All calls route through the OpenBB ``obb`` package when installed, falling back to clean mock/fallback structures when running in environments without openbb.
"""

import os
from typing import Any, Dict, List, Optional

# Import the OpenBB engine safely if installed; otherwise fallback gracefully.
try:
    from openbb import obb
except ImportError:
    obb = None

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

# ---------------------------------------------------------------------------
# Macro & Economic Intelligence
# ---------------------------------------------------------------------------

def get_macro_data(country: str = "united_states", indicator: str = "gdp", provider: str = "fred") -> Dict[str, Any]:
    """Fetch a macroeconomic indicator for a given country."""
    if obb is None:
        return {
            "indicator": indicator,
            "country": country,
            "provider": provider,
            "data": [{"date": "2026-01-01", "value": 3.75, "status": "simulated_fallback"}],
        }

    mapping = {
        "gdp": getattr(getattr(obb, "economy", None), "gdp", None),
        "cpi": getattr(getattr(obb, "economy", None), "cpi", None),
        "inflation": getattr(getattr(obb, "economy", None), "inflation", None),
        "unemployment": getattr(getattr(obb, "economy", None), "unemployment", None),
        "interest_rate": getattr(getattr(obb, "economy", None), "interest_rate", None),
    }
    func = mapping.get(indicator.lower())
    if func is None:
        return {
            "indicator": indicator,
            "country": country,
            "provider": provider,
            "data": [],
        }

    try:
        result = func(country=country, provider=provider)
        data = result.to_dict(orient="records") if hasattr(result, "to_dict") else (result if isinstance(result, list) else [result])
    except Exception as e:
        data = [{"error": str(e)}]

    return {
        "indicator": indicator,
        "country": country,
        "provider": provider,
        "data": data,
    }

# ---------------------------------------------------------------------------
# Equity Fundamentals & Market Depth
# ---------------------------------------------------------------------------

def get_equity_fundamentals(symbol: str, provider: str = "fmp") -> Dict[str, Any]:
    """Retrieve fundamental data for a ticker (balance sheet, income, cash flow)."""
    if obb is None:
        return {
            "symbol": symbol,
            "provider": provider,
            "fundamentals": [{"symbol": symbol, "pe_ratio": 28.5, "market_cap": 3000000000000, "status": "simulated_fallback"}],
        }

    try:
        func = getattr(getattr(obb, "equity", None), "fundamentals", None)
        if func:
            fundamentals = func(symbol=symbol, provider=provider)
            data = fundamentals.to_dict(orient="records") if hasattr(fundamentals, "to_dict") else [fundamentals]
        else:
            data = []
    except Exception as e:
        data = [{"error": str(e)}]

    return {
        "symbol": symbol,
        "provider": provider,
        "fundamentals": data,
    }

def get_equity_market_depth(symbol: str, provider: str = "polygon") -> Dict[str, Any]:
    """Get Level‑2 (order‑book) depth for a stock symbol."""
    if obb is None:
        return {
            "symbol": symbol,
            "provider": provider,
            "depth": {"bids": [], "asks": [], "status": "simulated_fallback"},
        }

    try:
        func = getattr(getattr(obb, "equity", None), "order_book", None)
        if func:
            depth = func(symbol=symbol, provider=provider)
            data = depth.to_dict(orient="records") if hasattr(depth, "to_dict") else depth
        else:
            data = {}
    except Exception as e:
        data = {"error": str(e)}

    return {
        "symbol": symbol,
        "provider": provider,
        "depth": data,
    }

def get_equity_price_history(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    provider: str = "yfinance",
) -> Dict[str, Any]:
    """Historical OHLCV price series for a ticker."""
    if obb is None:
        return {
            "symbol": symbol,
            "provider": provider,
            "prices": [{"date": "2026-10-20", "open": 230.0, "high": 235.0, "low": 229.0, "close": 234.5, "volume": 1000000}],
        }

    try:
        func = getattr(getattr(getattr(obb, "equity", None), "price", None), "historical", None)
        if func:
            price = func(symbol=symbol, start_date=start_date, end_date=end_date, provider=provider)
            data = price.to_dict(orient="records") if hasattr(price, "to_dict") else [price]
        else:
            data = []
    except Exception as e:
        data = [{"error": str(e)}]

    return {
        "symbol": symbol,
        "provider": provider,
        "prices": data,
    }

# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def get_news(limit: int = 20, source: str = "bloomberg", provider: str = "tiingo") -> List[Dict[str, Any]]:
    """Fetch the latest news headlines."""
    if obb is None:
        return [
            {
                "publishedDate": "2026-10-21T08:00:00Z",
                "title": "Markets Watch Global Central Bank Shifts and Tech Earnings Momentum",
                "source": "Bloomberg",
                "url": "https://www.bloomberg.com",
            }
        ]

    try:
        func = getattr(getattr(obb, "news", None), "world", None)
        if func:
            news_df = func(limit=limit, source=source, provider=provider)
            return news_df.to_dict(orient="records") if hasattr(news_df, "to_dict") else []
        return []
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Crypto
# ---------------------------------------------------------------------------

def get_crypto_price(symbol: str = "BTC-USD", start_date: Optional[str] = None, provider: str = "coingecko") -> Dict[str, Any]:
    """Historical price data for a cryptocurrency pair."""
    if obb is None:
        return {
            "symbol": symbol,
            "provider": provider,
            "prices": [{"date": "2026-10-20", "close": 68500.0, "volume": 25000000000}],
        }

    try:
        func = getattr(getattr(getattr(obb, "crypto", None), "price", None), "historical", None)
        if func:
            price = func(symbol=symbol, start_date=start_date, provider=provider)
            data = price.to_dict(orient="records") if hasattr(price, "to_dict") else [price]
        else:
            data = []
    except Exception as e:
        data = [{"error": str(e)}]

    return {
        "symbol": symbol,
        "provider": provider,
        "prices": data,
    }

if __name__ == "__main__":
    import json
    print(json.dumps({
        "macro": get_macro_data(),
        "equity_fundamentals": get_equity_fundamentals("AAPL"),
        "equity_price": get_equity_price_history("AAPL", start_date="2024-01-01"),
        "news": get_news(limit=5),
        "crypto": get_crypto_price("ETH-USD", start_date="2024-01-01"),
    }, indent=2, default=str))
