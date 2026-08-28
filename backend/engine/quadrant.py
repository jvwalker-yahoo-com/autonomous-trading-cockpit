"""
QuadrantModule classifying execution state into a 2x2 Risk vs Impact matrix.
"""
from typing import Dict
from .models import QuadrantOutput

class QuadrantModule:
    def quadrant(self, risk: float, impact: float) -> QuadrantOutput:
        """
        LOW: risk < 0.33 AND impact < 0.33
        MEDIUM: risk < 0.66 AND impact < 0.66
        HIGH: risk < 0.66 AND impact >= 0.66
        CRITICAL: else
        """
        risk_lvl = "LOW" if risk < 0.33 else ("MEDIUM" if risk < 0.66 else "HIGH")
        impact_lvl = "LOW" if impact < 0.33 else ("MEDIUM" if impact < 0.66 else "HIGH")

        if risk < 0.33 and impact < 0.33:
            q_name = "LOW"
            desc = "Optimal execution conditions. Low risk exposure and minimal footprint."
        elif risk < 0.66 and impact < 0.66:
            q_name = "MEDIUM"
            desc = "Moderate volatility/spreads. Standard algorithmic execution active."
        elif risk < 0.66 and impact >= 0.66:
            q_name = "HIGH"
            desc = "High market impact / low liquidity. Execution sizing throttled."
        else:
            q_name = "CRITICAL"
            desc = "Extreme risk threshold reached. Aggressive defense and stops enforced."

        return QuadrantOutput(
            quadrant=q_name,
            risk_level=risk_lvl,
            impact_level=impact_lvl,
            description=desc
        )
