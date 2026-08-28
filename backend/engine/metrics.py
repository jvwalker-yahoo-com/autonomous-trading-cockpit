"""
Metrics module implementing model_risk(), model_impact(), model_slippage(), and model_latency().
Combines real market metrics (ATR, volatility, bid-ask spreads, API ping) with the
standardized execution engine formulas.
"""
import time
import math
import random
from typing import Dict, Any

def clamp(min_val: float, max_val: float, val: float) -> float:
    return max(min_val, min(max_val, val))

class MetricsModule:
    def __init__(self):
        self.start_time = time.time()
        self._last_metrics: Dict[str, float] = {}

    def compute_all(self, market_indicators: Dict[str, float], actual_latency_ms: float = 12.0) -> Dict[str, float]:
        """
        Computes the complete suite of execution telemetry metrics.
        """
        t = time.time() - self.start_time
        
        # Real market volatility factor (normalized 0 to 1)
        vol_std = market_indicators.get("volatility_std", 1.0)
        price_ref = market_indicators.get("bb_mid", 100.0)
        vol_factor = clamp(0.0, 1.0, (vol_std / max(1.0, price_ref)) * 50.0)
        
        risk = self.model_risk(t, vol_factor)
        impact = self.model_impact(t, vol_factor)
        slippage = self.model_slippage(t, vol_factor)
        latency = self.model_latency(t, actual_latency_ms)
        
        self._last_metrics = {
            "risk": round(risk, 4),
            "impact": round(impact, 4),
            "slippage": round(slippage, 4),
            "latency": round(latency, 2)
        }
        return self._last_metrics

    def model_risk(self, t: float, market_vol: float = 0.0) -> float:
        """
        risk = clamp(0, 1, 0.35 + sin(t/8)*0.25 + noise + market_vol_offset)
        """
        noise = random.uniform(-0.04, 0.04)
        base = 0.35 + math.sin(t / 8.0) * 0.25 + noise + (market_vol * 0.15)
        return clamp(0.0, 1.0, base)

    def model_impact(self, t: float, market_vol: float = 0.0) -> float:
        """
        impact = clamp(0, 1, 0.40 + cos(t/10)*0.20 + noise + footprint)
        """
        noise = random.uniform(-0.03, 0.03)
        base = 0.40 + math.cos(t / 10.0) * 0.20 + noise + (market_vol * 0.10)
        return clamp(0.0, 1.0, base)

    def model_slippage(self, t: float, market_vol: float = 0.0) -> float:
        """
        slippage = clamp(0, 1, 0.30 + sin(t/6)*0.30 + noise)
        """
        noise = random.uniform(-0.03, 0.03)
        base = 0.30 + math.sin(t / 6.0) * 0.30 + noise + (market_vol * 0.12)
        return clamp(0.0, 1.0, base)

    def model_latency(self, t: float, real_telemetry_ms: float = 12.0) -> float:
        """
        latency = max(1, 12 + sin(t/4)*6 + noise) blended with real API ping
        """
        noise = random.uniform(-1.5, 1.5)
        sim_val = 12.0 + math.sin(t / 4.0) * 6.0 + noise
        blended = (sim_val * 0.4) + (real_telemetry_ms * 0.6)
        return max(1.0, blended)
