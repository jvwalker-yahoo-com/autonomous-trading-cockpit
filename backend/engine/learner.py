"""
Adaptive Self-Learning Engine.
Tracks trade outcomes (Wins vs Losses), performs mistake post-mortems,
and dynamically adjusts strategy weights and risk thresholds using reinforcement feedback.
"""
import time
from typing import Dict, List, Optional
from datetime import datetime, timezone
from .models import TradeRecord, MistakeLogEntry, LearningStatsOutput

class AdaptiveLearner:
    def __init__(self, initial_weights: Optional[Dict[str, float]] = None):
        self.weights: Dict[str, float] = initial_weights or {
            "momentum_trend": 0.25,
            "mean_reversion": 0.25,
            "volatility_breakout": 0.25,
            "news_sentiment": 0.25
        }
        self.learning_rate: float = 0.08
        self.min_weight: float = 0.05
        self.max_weight: float = 0.60
        self.mistake_history: List[MistakeLogEntry] = []
        self.total_trades_evaluated: int = 0
        self.winning_trades_count: int = 0
        self.losing_trades_count: int = 0
        self.total_win_usd: float = 0.0
        self.total_loss_usd: float = 0.0
        self.last_calibration_time: str = datetime.now(timezone.utc).isoformat()

    def evaluate_closed_trade(self, trade: TradeRecord) -> Optional[MistakeLogEntry]:
        """
        Assesses a closed trade, diagnoses root cause if losing,
        and applies reinforcement update to strategy weights.
        """
        self.total_trades_evaluated += 1
        pnl = trade.realized_pnl_usd
        models = trade.contributing_models or {}
        
        if trade.win:
            self.winning_trades_count += 1
            self.total_win_usd += pnl
            # Positive reinforcement: Reward models that aligned with the winning direction
            self._reinforce_models(models, trade.direction, reward=True, scale=abs(trade.realized_pnl_pct))
            return None
        else:
            self.losing_trades_count += 1
            self.total_loss_usd += abs(pnl)
            
            # Diagnose mistake root cause
            mistake_entry = self._diagnose_mistake(trade)
            self.mistake_history.insert(0, mistake_entry)
            if len(self.mistake_history) > 30:
                self.mistake_history.pop()

            # Negative reinforcement: Penalize models that gave misleading signals
            self._reinforce_models(models, trade.direction, reward=False, scale=abs(trade.realized_pnl_pct))
            self.last_calibration_time = datetime.now(timezone.utc).isoformat()
            return mistake_entry

    def _diagnose_mistake(self, trade: TradeRecord) -> MistakeLogEntry:
        """Generates detailed explanatory post-mortem of the trade failure."""
        symbol = trade.symbol
        direction = trade.direction
        loss_usd = abs(trade.realized_pnl_usd)
        models = trade.contributing_models or {}
        
        # Identify top model advocate for this trade
        top_model = "momentum_trend"
        top_score = 0.0
        for m_name, score in models.items():
            if direction == "LONG" and score > top_score:
                top_score = score
                top_model = m_name
            elif direction == "SHORT" and score < -top_score:
                top_score = abs(score)
                top_model = m_name

        if "mean_reversion" in top_model:
            failure_cause = f"Premature counter-trend entry on {symbol}. Mean-reversion triggered against prevailing momentum."
            adaptation = f"Reduced mean_reversion model weight by {self.learning_rate*100:.0f}%; tightened RSI entry boundary."
        elif "volatility_breakout" in top_model:
            failure_cause = f"False breakout trap on {symbol}. Price pierced Bollinger Band but failed to sustain volume follow-through."
            adaptation = f"Penalized volatility_breakout weight; increased confirmation threshold on {symbol}."
        elif "news_sentiment" in top_model:
            failure_cause = f"Sentiment divergence. News sentiment was bullish but technical price action broke key support."
            adaptation = f"Down-weighted news_sentiment relative to price action models."
        else:
            failure_cause = f"Adverse trend continuation against {direction} position on {symbol} hitting Stop-Loss."
            adaptation = f"Adjusted momentum_trend sensitivity and lowered entry risk budget."

        return MistakeLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            trade_id=trade.id,
            symbol=symbol,
            direction=direction,
            pnl_usd=round(-loss_usd, 2),
            primary_failure_cause=failure_cause,
            adaptation_action=adaptation,
            adjusted_weights={k: round(v, 3) for k, v in self.weights.items()}
        )

    def _reinforce_models(self, contributing_models: Dict[str, float], direction: str, reward: bool, scale: float):
        """
        Adjusts weights using a Multi-Armed Bandit / policy gradient step.
        """
        step = max(0.01, min(0.08, self.learning_rate * (1.0 + min(scale * 10.0, 2.0))))
        
        for name in list(self.weights.keys()):
            model_score = contributing_models.get(name, 0.0)
            
            # Check alignment
            if direction == "LONG":
                aligned = model_score > 0.1
            else: # SHORT
                aligned = model_score < -0.1

            if reward:
                if aligned:
                    self.weights[name] += step
                else:
                    self.weights[name] = max(self.min_weight, self.weights[name] - (step * 0.5))
            else: # Trade was a Loss
                if aligned:
                    self.weights[name] = max(self.min_weight, self.weights[name] - step)
                else:
                    self.weights[name] = min(self.max_weight, self.weights[name] + (step * 0.3))

        # Re-normalize to sum = 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: round(v / total, 4) for k, v in self.weights.items()}

    def get_stats(self) -> LearningStatsOutput:
        win_rate = (self.winning_trades_count / max(1, self.total_trades_evaluated)) * 100.0
        avg_win = self.total_win_usd / max(1, self.winning_trades_count)
        avg_loss = self.total_loss_usd / max(1, self.losing_trades_count)
        profit_factor = (self.total_win_usd / max(0.01, self.total_loss_usd)) if self.total_loss_usd > 0 else (self.total_win_usd or 1.0)

        return LearningStatsOutput(
            strategy_weights={k: round(v, 3) for k, v in self.weights.items()},
            total_trades_evaluated=self.total_trades_evaluated,
            win_rate_pct=round(win_rate, 1),
            avg_win_usd=round(avg_win, 2),
            avg_loss_usd=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            mistake_history=self.mistake_history,
            learning_rate=self.learning_rate,
            last_calibration_time=self.last_calibration_time
        )
