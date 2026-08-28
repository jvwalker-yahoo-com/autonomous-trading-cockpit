"""
FederationModule managing multi-model scoring, strategy weighting, and ensemble consensus.
Evaluates Trend Following (Momentum), Mean Reversion, Volatility Breakout, and Sentiment models.
"""
from typing import Dict, List, Tuple
from .models import FederationOutput, ModelSignal

class FederationModule:
    def __init__(self):
        # Default baseline weights across strategies
        self.strategy_names = [
            "momentum_trend",
            "mean_reversion",
            "volatility_breakout",
            "news_sentiment"
        ]

    def score_momentum_trend(self, indicators: Dict[str, float], price: float) -> Tuple[float, str, str]:
        """EMA(9) vs EMA(21) + MACD direction."""
        ema_9 = indicators.get("ema_9", price)
        ema_21 = indicators.get("ema_21", price)
        macd = indicators.get("macd_line", 0.0)
        
        diff_pct = (ema_9 - ema_21) / max(1.0, ema_21)
        score = max(-1.0, min(1.0, diff_pct * 80.0 + (macd * 0.5)))
        
        if score > 0.25:
            sig = "BUY"
            rationale = f"EMA(9) {ema_9:.2f} > EMA(21) {ema_21:.2f} with positive MACD ({macd:+.2f})"
        elif score < -0.25:
            sig = "SHORT"
            rationale = f"EMA(9) {ema_9:.2f} < EMA(21) {ema_21:.2f} with negative MACD ({macd:+.2f})"
        else:
            sig = "NEUTRAL"
            rationale = "EMAs converging; no directional trend dominance"
        return round(score, 3), sig, rationale

    def score_mean_reversion(self, indicators: Dict[str, float], price: float) -> Tuple[float, str, str]:
        """RSI(14) + Bollinger Bands %B oversold/overbought."""
        rsi = indicators.get("rsi_14", 50.0)
        bb_upper = indicators.get("bb_upper", price * 1.02)
        bb_lower = indicators.get("bb_lower", price * 0.98)
        bb_width = max(0.01, bb_upper - bb_lower)
        pct_b = (price - bb_lower) / bb_width

        # Invert: oversold (low RSI/pct_b) -> bullish mean-reversion (+ score)
        # overbought (high RSI/pct_b) -> bearish mean-reversion (- score)
        score = 0.0
        if rsi < 35.0 or pct_b < 0.15:
            score = max(0.3, min(1.0, (40.0 - rsi) / 25.0 + (0.3 - pct_b)))
            sig = "BUY"
            rationale = f"RSI oversold ({rsi:.1f}) near lower Bollinger Band ({bb_lower:.2f})"
        elif rsi > 65.0 or pct_b > 0.85:
            score = max(-1.0, min(-0.3, (60.0 - rsi) / 25.0 - (pct_b - 0.7)))
            sig = "SHORT"
            rationale = f"RSI overbought ({rsi:.1f}) near upper Bollinger Band ({bb_upper:.2f})"
        else:
            sig = "NEUTRAL"
            rationale = f"RSI neutral ({rsi:.1f}) inside Bollinger mid-channel"
        return round(score, 3), sig, rationale

    def score_volatility_breakout(self, indicators: Dict[str, float], price: float) -> Tuple[float, str, str]:
        """Breakout through Bollinger envelope with expanding volatility."""
        bb_upper = indicators.get("bb_upper", price * 1.02)
        bb_lower = indicators.get("bb_lower", price * 0.98)
        atr = indicators.get("atr", price * 0.015)
        
        if price > bb_upper:
            dist = (price - bb_upper) / max(0.01, atr)
            score = min(1.0, 0.4 + dist * 0.3)
            sig = "BUY"
            rationale = f"Price {price:.2f} breaking above Upper Band {bb_upper:.2f} (ATR: {atr:.2f})"
        elif price < bb_lower:
            dist = (bb_lower - price) / max(0.01, atr)
            score = max(-1.0, -0.4 - dist * 0.3)
            sig = "SHORT"
            rationale = f"Price {price:.2f} breaking below Lower Band {bb_lower:.2f} (ATR: {atr:.2f})"
        else:
            score = 0.0
            sig = "NEUTRAL"
            rationale = "Price oscillating within normal volatility envelope"
        return round(score, 3), sig, rationale

    def score_news_sentiment(self, sentiment_val: float) -> Tuple[float, str, str]:
        """Finnhub / NLP sentiment index."""
        score = max(-1.0, min(1.0, sentiment_val))
        if score > 0.20:
            sig = "BUY"
            rationale = f"Positive market news flow and institutional sentiment score (+{score:.2f})"
        elif score < -0.20:
            sig = "SHORT"
            rationale = f"Negative headline sentiment and risk-off pressure score ({score:.2f})"
        else:
            sig = "NEUTRAL"
            rationale = f"Neutral market news coverage ({score:+.2f})"
        return round(score, 3), sig, rationale

    def model_federation(self, indicators: Dict[str, float], price: float, sentiment_val: float, current_weights: Dict[str, float]) -> FederationOutput:
        """
        Executes multi-model scoring, applies dynamically calibrated weights,
        and determines consensus winner.
        """
        s_mom, sig_mom, rat_mom = self.score_momentum_trend(indicators, price)
        s_mr, sig_mr, rat_mr = self.score_mean_reversion(indicators, price)
        s_bo, sig_bo, rat_bo = self.score_volatility_breakout(indicators, price)
        s_sent, sig_sent, rat_sent = self.score_news_sentiment(sentiment_val)

        scores_map = {
            "momentum_trend": s_mom,
            "mean_reversion": s_mr,
            "volatility_breakout": s_bo,
            "news_sentiment": s_sent
        }

        # Normalize weights
        total_w = sum(current_weights.get(k, 0.25) for k in self.strategy_names)
        if total_w <= 0:
            total_w = 1.0
        normalized_weights = {k: current_weights.get(k, 0.25) / total_w for k in self.strategy_names}

        # Calculate weighted consensus score
        weighted_score = sum(scores_map[k] * normalized_weights[k] for k in self.strategy_names)

        # Determine highest contributor / dominant model
        dominant_model = max(self.strategy_names, key=lambda k: abs(scores_map[k]) * normalized_weights[k])

        model_details = [
            ModelSignal(name="Momentum Trend (EMA/MACD)", signal=sig_mom, score=s_mom, weight=round(normalized_weights["momentum_trend"], 3), rationale=rat_mom),
            ModelSignal(name="Mean Reversion (RSI/BB)", signal=sig_mr, score=s_mr, weight=round(normalized_weights["mean_reversion"], 3), rationale=rat_mr),
            ModelSignal(name="Volatility Breakout", signal=sig_bo, score=s_bo, weight=round(normalized_weights["volatility_breakout"], 3), rationale=rat_bo),
            ModelSignal(name="News Sentiment (Finnhub)", signal=sig_sent, score=s_sent, weight=round(normalized_weights["news_sentiment"], 3), rationale=rat_sent),
        ]

        return FederationOutput(
            outputs=scores_map,
            weights={k: round(v, 3) for k, v in normalized_weights.items()},
            federation=dominant_model,
            federated_score=round(weighted_score, 4),
            model_details=model_details
        )
