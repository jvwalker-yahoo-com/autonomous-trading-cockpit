"""
ArbitrationModule enforcing safety constraints, risk gate verification,
portfolio exposure limits, drawdown circuit breakers, and final execution mode.
"""
from typing import Dict, List, Optional
from .models import ArbitrationOutput

class ArbitrationModule:
    def arbitration(
        self,
        main_mode: str,
        quadrant: str,
        anomaly_detected: bool,
        current_drawdown_pct: float,
        max_drawdown_limit_pct: float,
        current_exposure_pct: float,
        max_exposure_limit_pct: float,
        active_positions_count: int,
        max_concurrent_positions: int = 5,
        market_open: bool = True,
        enforce_market_hours: bool = True
    ) -> ArbitrationOutput:
        """
        Arbitrates final execution mode and trade clearance based on risk gates and market hours.
        """
        reasons = []
        approved = True
        circuit_breaker = False
        final_mode = main_mode

        # 0. Market Hours Gate (eToro UK: 14:30 - 21:00 UK Time)
        if enforce_market_hours and not market_open:
            approved = False
            reasons.append("Outside eToro UK US-market trading hours (14:30 - 21:00 UK / Mon-Fri)")

        # 1. Max Drawdown Circuit Breaker
        if current_drawdown_pct >= max_drawdown_limit_pct:
            approved = False
            circuit_breaker = True
            final_mode = "HALTED"
            reasons.append(f"CIRCUIT BREAKER: Max drawdown limit reached ({current_drawdown_pct*100:.1f}% >= {max_drawdown_limit_pct*100:.1f}%)")

        # 2. Critical Regime or Anomaly Intercept
        if main_mode == "CRITICAL" or quadrant == "CRITICAL":
            final_mode = "WARN" if not circuit_breaker else "HALTED"
            if anomaly_detected:
                reasons.append("CRITICAL quadrant anomaly active: Execution restricted to defensive/exit orders only")

        # 3. Portfolio Exposure Gate
        exposure_ok = current_exposure_pct < max_exposure_limit_pct
        if not exposure_ok:
            approved = False
            reasons.append(f"Max portfolio exposure reached ({current_exposure_pct*100:.1f}% >= {max_exposure_limit_pct*100:.1f}%)")

        # 4. Position Concentration Gate
        if active_positions_count >= max_concurrent_positions:
            approved = False
            reasons.append(f"Max concurrent positions reached ({active_positions_count}/{max_concurrent_positions})")

        # 5. Passed all gates
        if approved and not reasons:
            reasons.append("All arbitration safety checks passed. Execution permitted.")

        return ArbitrationOutput(
            main_mode=main_mode,
            final_mode=final_mode,
            approved=approved,
            risk_gate_passed=(not anomaly_detected and quadrant != "CRITICAL"),
            drawdown_ok=(not circuit_breaker),
            exposure_ok=exposure_ok,
            circuit_breaker_active=circuit_breaker,
            reasons=reasons
        )
