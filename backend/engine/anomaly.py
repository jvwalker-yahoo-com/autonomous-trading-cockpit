"""
AnomalyModule detecting risk/impact/slippage spikes, EWMA shifts,
and statistical Z-score anomalies in price/volume action.
"""
import numpy as np
from typing import Dict, List
from .models import AnomalyDetectorOutput

class AnomalyModule:
    def __init__(self):
        self.ewma_price: float = 0.0
        self.alpha: float = 0.15 # EWMA smoothing factor

    def anomaly_detector(self, metrics: Dict[str, float], price_history: List[float], volume_history: List[float]) -> AnomalyDetectorOutput:
        """
        Detects anomalies according to PDF specification:
        - risk_spike = risk > 0.85
        - impact_jump = impact > 0.85
        - slippage_jump = slippage > 0.85
        - latency_spike = latency > 20
        Plus EWMA & Z-Score anomaly detectors.
        """
        risk = metrics.get("risk", 0.0)
        impact = metrics.get("impact", 0.0)
        slippage = metrics.get("slippage", 0.0)
        latency = metrics.get("latency", 0.0)

        risk_spike = risk > 0.85
        impact_jump = impact > 0.85
        slippage_jump = slippage > 0.85
        latency_spike = latency > 20.0

        anomalies_list = []
        if risk_spike:
            anomalies_list.append(f"Risk Spike detected ({risk:.2f} > 0.85)")
        if impact_jump:
            anomalies_list.append(f"Market Impact Jump detected ({impact:.2f} > 0.85)")
        if slippage_jump:
            anomalies_list.append(f"Slippage Jump detected ({slippage:.2f} > 0.85)")
        if latency_spike:
            anomalies_list.append(f"Telemetry Latency Spike ({latency:.1f}ms > 20ms)")

        # Z-Score on price returns
        z_score_price = 0.0
        if len(price_history) >= 20:
            prices = np.array(price_history)
            mean = np.mean(prices[-20:])
            std = np.std(prices[-20:])
            if std > 0:
                z_score_price = (prices[-1] - mean) / std
                if abs(z_score_price) > 2.5:
                    anomalies_list.append(f"Price Z-Score Outlier ({z_score_price:.2f}σ)")

        # Z-Score on volume
        z_score_vol = 0.0
        if len(volume_history) >= 20:
            vols = np.array(volume_history)
            v_mean = np.mean(vols[-20:])
            v_std = np.std(vols[-20:])
            if v_std > 0:
                z_score_vol = (vols[-1] - v_mean) / v_std
                if z_score_vol > 2.8:
                    anomalies_list.append(f"Volume Surge Flash ({z_score_vol:.1f}σ volume spike)")

        anomaly_detected = len(anomalies_list) > 0

        return AnomalyDetectorOutput(
            risk_spike=risk_spike,
            impact_jump=impact_jump,
            slippage_jump=slippage_jump,
            latency_spike=latency_spike,
            z_score_price=round(float(z_score_price), 2),
            z_score_vol=round(float(z_score_vol), 2),
            anomaly_detected=anomaly_detected,
            anomalies=anomalies_list
        )
