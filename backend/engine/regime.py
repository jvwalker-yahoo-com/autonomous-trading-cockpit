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

        # JEV-style 6-Regime Detection
        bb_width_pct = indicators.get("bb_width_pct", 0.0)  # Bollinger Band width as % of price
        atr_pct = indicators.get("atr_pct", 0.0)            # ATR as % of price
        rsi_val = indicators.get("rsi_14", 50.0)
        vol_surge = indicators.get("volume_surge", 1.0)

        in_crisis = (risk > 0.70 or impact > 0.75 or (bb_width_pct > 0.06 and vol_surge > 2.5))
        is_vol_expanding = (bb_width_pct > 0.035 and not in_crisis)
        is_vol_contracting = (bb_width_pct < 0.015 and adx < 20.0)

        if in_crisis:
            trend = "CRISIS"
        elif adx >= 25.0 and ema_9 > ema_21 and st_dir == 1.0:
            trend = "BULL_TREND"
        elif adx >= 25.0 and ema_9 < ema_21 and st_dir == -1.0:
            trend = "BEAR_TREND"
        elif is_vol_expanding:
            trend = "VOL_EXPANSION"
        elif is_vol_contracting:
            trend = "VOL_CONTRACTION"
        elif (rsi_val < 42.0 or rsi_val > 58.0) and adx >= 18.0:
            trend = "MEAN_REVERSION"
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
