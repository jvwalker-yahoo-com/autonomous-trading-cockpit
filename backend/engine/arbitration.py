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
        max_concurrent_positions: int = 8,
        market_open: bool = True,
        session_msg: Optional[str] = None,
        enforce_market_hours: bool = True,
        # Enhanced Risk Engine & Day Trading parameters
        daily_drawdown_usd: float = 0.0,
        max_daily_loss_usd: float = 35.0,
        daily_drawdown_pct: float = 0.0,
        max_daily_loss_pct: float = 0.025,
        estimated_spread_pct: float = 0.0005,
        max_spread_pct_day_trade: float = 0.0015,
        active_day_trades: int = 0,
        max_active_day_trades: int = 4,
        day_trading_enabled: bool = True,
        regime_trend: str = "CHOPPY"
    ) -> ArbitrationOutput:
        """
        Arbitrates final execution mode and trade clearance based on risk gates,
        daily loss circuit breakers, spread filters, and market hours.
        """
        reasons = []
        approved = True
        circuit_breaker = False
        daily_loss_cb = False
        spread_filter_ok = True
        day_trade_ok = day_trading_enabled
        final_mode = main_mode

        # 0. Market Hours Gate: Check trading hours before clearing trades
        if enforce_market_hours and not market_open:
            approved = False
            msg = session_msg or "Outside eToro UK trading hours (14:30 - 21:00 UK / Mon-Fri)"
            reasons.append(f"Market Closed: {msg}")

        # 1. Max Overall Portfolio Drawdown Circuit Breaker
        if current_drawdown_pct >= max_drawdown_limit_pct:
            approved = False
            circuit_breaker = True
            final_mode = "HALTED"
            reasons.append(f"CIRCUIT BREAKER: Max portfolio drawdown reached ({current_drawdown_pct*100:.1f}% >= {max_drawdown_limit_pct*100:.1f}%)")

        # 2. Intraday Daily Loss Circuit Breaker (stops day-trade bleeding)
        if daily_drawdown_usd >= max_daily_loss_usd or daily_drawdown_pct >= max_daily_loss_pct:
            daily_loss_cb = True
            day_trade_ok = False
            reasons.append(f"DAILY LOSS CIRCUIT BREAKER: Daily loss limit hit (${daily_drawdown_usd:.2f} >= ${max_daily_loss_usd:.2f} or {daily_drawdown_pct*100:.1f}% >= {max_daily_loss_pct*100:.1f}%). New day trades halted.")

        # 3. Critical Regime or Anomaly Intercept
        if main_mode == "CRITICAL" or quadrant == "CRITICAL":
            final_mode = "WARN" if not circuit_breaker else "HALTED"
            if anomaly_detected:
                reasons.append("CRITICAL quadrant anomaly active: Execution restricted to defensive/exit orders only")

        # 3b. JEV CRISIS Regime Gate: block new entries during crisis/turbulence
        if regime_trend == "CRISIS":
            approved = False
            reasons.append("JEV CRISIS regime detected: all new entries blocked (hold & re-evaluate)")

        # 4. Portfolio Exposure Gate
        exposure_ok = current_exposure_pct < max_exposure_limit_pct
        if not exposure_ok:
            approved = False
            reasons.append(f"Max portfolio exposure reached ({current_exposure_pct*100:.1f}% >= {max_exposure_limit_pct*100:.1f}%)")

        # 5. Position Concentration Gate (Total Portfolio)
        if active_positions_count >= max_concurrent_positions:
            approved = False
            reasons.append(f"Max concurrent positions reached ({active_positions_count}/{max_concurrent_positions})")

        # 6. Day Trading Specific Risk Gates
        if not day_trading_enabled:
            day_trade_ok = False
        else:
            if active_day_trades >= max_active_day_trades:
                day_trade_ok = False
                reasons.append(f"Max active day trades reached ({active_day_trades}/{max_active_day_trades})")

            # Spread filter for intraday trades
            if estimated_spread_pct > max_spread_pct_day_trade:
                spread_filter_ok = False
                day_trade_ok = False
                reasons.append(f"Spread filter tripped: spread ({estimated_spread_pct*100:.3f}%) exceeds day trading threshold ({max_spread_pct_day_trade*100:.3f}%)")

        # 7. Passed all gates
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
            daily_loss_circuit_breaker_active=daily_loss_cb,
            spread_filter_passed=spread_filter_ok,
            day_trade_approved=day_trade_ok and approved and not daily_loss_cb,
            reasons=reasons
        )
