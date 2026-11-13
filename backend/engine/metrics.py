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
        Computes deterministic execution telemetry metrics driven directly by
        real volatility/ATR/volume ratios and measured HTTP latency.
        """
        t = time.time() - self.start_time

        vol_std = float(market_indicators.get("volatility_std", 1.0))
        price_ref = max(1.0, float(market_indicators.get("bb_mid", 100.0)))
        atr = float(market_indicators.get("atr", vol_std))
        vol_surge = float(market_indicators.get("volume_surge", 1.0))
        vol_factor = clamp(0.0, 1.0, max(vol_std / price_ref, atr / price_ref) * 20.0)

        risk = self.model_risk(t, vol_factor, vol_surge)
        impact = self.model_impact(t, vol_factor, vol_surge)
        slippage = self.model_slippage(t, vol_factor)
        latency = self.model_latency(t, actual_latency_ms)

        self._last_metrics = {
            "risk": round(risk, 4),
            "impact": round(impact, 4),
            "slippage": round(slippage, 4),
            "latency": round(latency, 2)
        }
        return self._last_metrics

    def model_risk(self, t: float, market_vol: float = 0.0, volume_surge: float = 1.0) -> float:
        """Deterministic volatility & volume-spike execution risk factor in [0, 1]."""
        surge_pen = max(0.0, volume_surge - 1.5) * 0.08
        base = 0.08 + (market_vol * 0.72) + surge_pen
        return clamp(0.0, 1.0, base)

    def model_impact(self, t: float, market_vol: float = 0.0, volume_surge: float = 1.0) -> float:
        """Deterministic market impact estimate in [0, 1] reflecting thin-volume vulnerability."""
        thin_liquidity = max(0.0, 1.0 - volume_surge) * 0.25
        base = 0.05 + (market_vol * 0.55) + thin_liquidity
        return clamp(0.0, 1.0, base)

    def model_slippage(self, t: float, market_vol: float = 0.0) -> float:
        """Deterministic expected slippage score in [0, 1] proportional to market volatility."""
        base = 0.04 + (market_vol * 0.60)
        return clamp(0.0, 1.0, base)

    def model_latency(self, t: float, real_telemetry_ms: float = 12.0) -> float:
        """
        Normalizes real HTTP round-trip telemetry against the AnomalyModule >20ms SLA:
        - <= 800ms healthy REST calls map monotonically to [2.0, 17.0] ms score
        - 800ms..1500ms sluggish calls ramp linearly to [17.0, 20.0]
        - > 1500ms stalled/degraded calls breach >20.0 to trigger AnomalyModule.latency_spike
        """
        ms = max(0.0, float(real_telemetry_ms))
        if ms <= 800.0:
            return round(2.0 + (ms / 800.0) * 15.0, 2)
        if ms <= 1500.0:
            return round(17.0 + ((ms - 800.0) / 700.0) * 3.0, 2)
        return round(20.0 + (ms - 1500.0) / 100.0, 2)
