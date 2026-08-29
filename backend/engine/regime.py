"""
RegimeModule classifying the market regime into OK, WARN, or CRITICAL based on
aggregate telemetry risk scores and technical trend states.
"""
from typing import Dict, List
from .models import RegimeState

class RegimeModule:
    def __init__(self):
        self.recent_events: List[str] = []

    def model_mode(self, metrics: Dict[str, float], indicators: Dict[str, float]) -> RegimeState:
        """
        Computes score = (risk + impact + slippage) / 3
        if score < 0.33: OK
        elif score < 0.66: WARN
        else: CRITICAL
        """
        risk = metrics.get("risk", 0.35)
        impact = metrics.get("impact", 0.40)
        slippage = metrics.get("slippage", 0.30)
        latency = metrics.get("latency", 12.0)

        score = (risk + impact + slippage) / 3.0
        
        if score < 0.33:
            mode = "OK"
        elif score < 0.66:
            mode = "WARN"
        else:
            mode = "CRITICAL"

        # Determine structural trend using cinar/indicator ADX & SuperTrend
        ema_9 = indicators.get("ema_9", 100.0)
        ema_21 = indicators.get("ema_21", 100.0)
        rsi = indicators.get("rsi_14", 50.0)
        macd = indicators.get("macd_line", 0.0)
        adx = indicators.get("adx", 22.0)
        st_dir = indicators.get("supertrend_dir", 1.0)

        if adx < 20.0:
            trend = "CHOPPY"
        elif ema_9 > ema_21 and rsi > 50.0 and st_dir == 1.0:
            trend = "BULL_TREND"
        elif ema_9 < ema_21 and rsi < 50.0 and st_dir == -1.0:
            trend = "BEAR_TREND"
        else:
            trend = "CHOPPY"

        # Manage event timeline
        event_str = f"Regime {mode} (Score: {score:.2f}) | Trend: {trend} | Latency: {latency:.1f}ms"
        if not self.recent_events or self.recent_events[-1] != event_str:
            self.recent_events.append(event_str)
            if len(self.recent_events) > 25:
                self.recent_events.pop(0)

        return RegimeState(
            risk=risk,
            impact=impact,
            slippage=slippage,
            latency=latency,
            score=round(score, 4),
            mode=mode,
            trend=trend,
            events=list(reversed(self.recent_events[-10:]))
        )
