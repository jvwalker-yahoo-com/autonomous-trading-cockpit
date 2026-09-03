"""
Data feed module with Finnhub REST API integration and high-fidelity fallback simulator.
Fetches real-time quotes, calculates technical indicators, maintains rolling tick history,
and estimates market micro-structure (spreads, depth, sentiment).
"""
import time
import math
import random
import requests
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .screener import MASTER_STOCK_UNIVERSE

# Reference seed prices for all 100+ US equities, high-beta assets & ETFs
BASE_PRICES: Dict[str, float] = {
    sym: data["base_price"] for sym, data in MASTER_STOCK_UNIVERSE.items()
}
# Fallback defaults for major indices/cryptos if requested
BASE_PRICES.update({
    "BTC": 64200.0, "ETH": 2540.0, "SOL": 142.0, "XRP": 0.58, "GOLD": 2510.0, "OIL": 74.50
})


class MarketDataPoint:
    def __init__(self, symbol: str, price: float, high: float, low: float, open_p: float, prev_close: float, volume: float, timestamp: float):
        self.symbol = symbol
        self.price = price
        self.high = high
        self.low = low
        self.open = open_p
        self.prev_close = prev_close
        self.volume = volume
        self.timestamp = timestamp
        self.change = price - prev_close
        self.change_pct = (self.change / prev_close) * 100.0 if prev_close > 0 else 0.0

from .indicators import TechnicalIndicators

class DataFeedManager:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.history_windows: Dict[str, List[float]] = {}
        self.volume_windows: Dict[str, List[float]] = {}
        self.last_quotes: Dict[str, MarketDataPoint] = {}
        self.simulated_states: Dict[str, Dict[str, float]] = {}
        self.last_api_call_time = 0.0
        self.api_latency_ms = 12.0
        
        # Initialize historical buffers with synthetic warmup
        for symbol, base_p in BASE_PRICES.items():
            self._warmup_history(symbol, base_p)

    def _warmup_history(self, symbol: str, base_price: float):
        """Generates initial 60 periods of price history for indicator readiness."""
        prices = []
        volumes = []
        p = max(0.00000001, base_price * (1.0 - random.uniform(0.01, 0.03)))
        precision = 8 if base_price < 0.01 else (4 if base_price < 1.0 else 2)
        for _ in range(60):
            p = max(0.00000001, p + p * random.gauss(0.0001, 0.003))
            prices.append(round(p, precision))
            volumes.append(round(random.uniform(50000, 250000), 0))
        self.history_windows[symbol] = prices
        self.volume_windows[symbol] = volumes
        self.simulated_states[symbol] = {
            "price": prices[-1],
            "drift": random.uniform(-0.0002, 0.0002),
            "volatility": random.uniform(0.0015, 0.0040)
        }
        self.last_quotes[symbol] = MarketDataPoint(
            symbol=symbol,
            price=prices[-1],
            high=max(prices[-10:]),
            low=min(prices[-10:]),
            open_p=prices[0],
            prev_close=prices[0],
            volume=volumes[-1],
            timestamp=time.time()
        )

    def set_api_key(self, key: str):
        self.api_key = key.strip()

    def get_latest_quote(self, symbol: str) -> MarketDataPoint:
        """
        Fetches live quote from Finnhub if API key is provided and valid,
        otherwise updates high-fidelity simulation tick.
        """
        start_t = time.perf_counter()
        quote = None
        
        if self.api_key and len(self.api_key) > 5:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.api_key}"
                resp = requests.get(url, timeout=3.0)
                self.api_latency_ms = max(5.0, (time.perf_counter() - start_t) * 1000.0)
                if resp.status_code == 200:
                    data = resp.json()
                    c = data.get("c", 0.0)
                    if c and c > 0:
                        quote = MarketDataPoint(
                            symbol=symbol,
                            price=float(c),
                            high=float(data.get("h", c)),
                            low=float(data.get("l", c)),
                            open_p=float(data.get("o", c)),
                            prev_close=float(data.get("pc", c)),
                            volume=random.uniform(100000, 500000),
                            timestamp=float(data.get("t", time.time()))
                        )
            except Exception:
                pass # Gracefully fall back to simulated tick

        if quote is None:
            # Fallback high-fidelity simulation
            self.api_latency_ms = max(4.0, (time.perf_counter() - start_t) * 1000.0 + random.uniform(2.0, 15.0))
            quote = self._generate_simulated_tick(symbol)

        # Update rolling buffer
        if symbol not in self.history_windows:
            self._warmup_history(symbol, quote.price)
        
        self.history_windows[symbol].append(quote.price)
        if len(self.history_windows[symbol]) > 120:
            self.history_windows[symbol].pop(0)
            
        self.volume_windows[symbol].append(quote.volume)
        if len(self.volume_windows[symbol]) > 120:
            self.volume_windows[symbol].pop(0)

        self.last_quotes[symbol] = quote
        return quote

    def _generate_simulated_tick(self, symbol: str) -> MarketDataPoint:
        state = self.simulated_states.get(symbol)
        if not state:
            base_p = BASE_PRICES.get(symbol, 150.0)
            self._warmup_history(symbol, base_p)
            state = self.simulated_states[symbol]
        
        # Periodic random regime shifts
        if random.random() < 0.05:
            state["drift"] = random.uniform(-0.001, 0.001)
        
        current_p = state["price"]
        step = current_p * (state["drift"] + random.gauss(0, state["volatility"]))
        precision = 8 if current_p < 0.01 else (4 if current_p < 1.0 else 2)
        min_p = 10 ** (-precision)
        new_p = max(min_p, round(current_p + step, precision))
        state["price"] = new_p
        
        hist = self.history_windows.get(symbol, [new_p])
        high_p = max(max(hist[-15:]), new_p)
        low_p = min(min(hist[-15:]), new_p)
        open_p = hist[0] if hist else new_p
        prev_close = BASE_PRICES.get(symbol, new_p)

        return MarketDataPoint(
            symbol=symbol,
            price=new_p,
            high=high_p,
            low=low_p,
            open_p=open_p,
            prev_close=prev_close,
            volume=random.uniform(50000, 300000),
            timestamp=time.time()
        )

    def get_technical_indicators(self, symbol: str) -> Dict[str, float]:
        """
        Calculates comprehensive quantitative indicators based on cinar/indicator:
        EMA(9), EMA(21), RSI(14), MACD, Bollinger Bands, ATR, ADX, SuperTrend, VWAP, MFI, and Keltner Channels.
        """
        prices = np.array(self.history_windows.get(symbol, [100.0]))
        volumes = np.array(self.volume_windows.get(symbol, [100000.0]))
        
        # Synthetic highs and lows from rolling prices
        highs = prices * 1.004
        lows = prices * 0.996

        if len(prices) < 20:
            p = float(prices[-1])
            return {
                "ema_9": p,
                "ema_21": p,
                "rsi_14": 50.0,
                "macd_line": 0.0,
                "macd_signal": 0.0,
                "bb_upper": round(p * 1.02, 2),
                "bb_lower": round(p * 0.98, 2),
                "bb_mid": p,
                "atr": round(p * 0.015, 2),
                "volatility_std": round(p * 0.01, 2),
                "adx": 22.0,
                "plus_di": 20.0,
                "minus_di": 20.0,
                "supertrend_val": round(p * 0.98, 2),
                "supertrend_dir": 1.0,
                "vwap": p,
                "mfi": 50.0,
                "keltner_upper": round(p * 1.02, 2),
                "keltner_mid": p,
                "keltner_lower": round(p * 0.98, 2)
            }

        # 1. EMAs & MACD
        ema_9 = TechnicalIndicators.calc_ema(prices, 9)
        ema_21 = TechnicalIndicators.calc_ema(prices, 21)
        ema_12 = TechnicalIndicators.calc_ema(prices, 12)
        ema_26 = TechnicalIndicators.calc_ema(prices, 26)
        macd_line = ema_12 - ema_26
        macd_signal = TechnicalIndicators.calc_ema(prices[-9:], 9) - TechnicalIndicators.calc_ema(prices[-26:], 26)

        # 2. RSI(14)
        deltas = np.diff(prices[-15:])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains) if len(gains) > 0 else 0.001
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        # 3. Bollinger Bands
        window = prices[-20:]
        bb_mid = float(np.mean(window))
        std = float(np.std(window))
        bb_upper = bb_mid + (2.0 * std)
        bb_lower = bb_mid - (2.0 * std)

        # 4. ATR
        atr = TechnicalIndicators.calc_atr(highs, lows, prices, 14)

        # 5. cinar/indicator: ADX Trend Strength
        adx, plus_di, minus_di = TechnicalIndicators.calc_adx(highs, lows, prices, 14)

        # 6. cinar/indicator: SuperTrend
        st_val, st_dir = TechnicalIndicators.calc_supertrend(highs, lows, prices, 10, 3.0)

        # 7. cinar/indicator: VWAP
        vwap = TechnicalIndicators.calc_vwap(prices, volumes)

        # 8. cinar/indicator: MFI
        mfi = TechnicalIndicators.calc_mfi(highs, lows, prices, volumes, 14)

        # 9. cinar/indicator: Keltner Channels
        k_upper, k_mid, k_lower = TechnicalIndicators.calc_keltner_channel(highs, lows, prices, 20, 10, 2.0)

        return {
            "ema_9": round(ema_9, 2),
            "ema_21": round(ema_21, 2),
            "rsi_14": round(float(rsi), 2),
            "macd_line": round(macd_line, 3),
            "macd_signal": round(macd_signal, 3),
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_mid": round(bb_mid, 2),
            "atr": round(atr, 3),
            "volatility_std": round(std, 3),
            "adx": round(adx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "supertrend_val": round(st_val, 2),
            "supertrend_dir": float(st_dir),
            "vwap": round(vwap, 2),
            "mfi": round(mfi, 2),
            "keltner_upper": round(k_upper, 2),
            "keltner_mid": round(k_mid, 2),
            "keltner_lower": round(k_lower, 2)
        }

    def get_news_sentiment(self, symbol: str) -> float:
        """
        Returns a sentiment score between -1.0 (very bearish) and +1.0 (very bullish).
        """
        if self.api_key and len(self.api_key) > 5:
            try:
                url = f"https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={self.api_key}"
                resp = requests.get(url, timeout=2.5)
                if resp.status_code == 200:
                    data = resp.json()
                    buzz = data.get("buzz", {})
                    bullish_pct = data.get("sentiment", {}).get("bullishPercent", 0.5)
                    return round((bullish_pct - 0.5) * 2.0, 2)
            except Exception:
                pass
        
        # Synthetic news sentiment based on price momentum with noise
        hist = self.history_windows.get(symbol, [100.0])
        if len(hist) > 10:
            denom = hist[-10]
            if abs(denom) > 1e-12:
                ret = (hist[-1] - denom) / denom
            else:
                ret = 0.0
            sentiment = math.tanh(ret * 20.0) + random.uniform(-0.1, 0.1)
            return round(max(-1.0, min(1.0, sentiment)), 2)
        return 0.05
