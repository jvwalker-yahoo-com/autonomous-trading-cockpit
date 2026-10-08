"""
FederationModule managing multi-model scoring, strategy weighting, and ensemble consensus.
Evaluates Trend Following (Momentum), Mean Reversion, Volatility Breakout, and Sentiment models.
"""
from typing import Dict, List, Tuple, Any, Optional
from .models import FederationOutput, ModelSignal

class FederationModule:
    def __init__(self):
        # Default baseline weights across strategies
        self.strategy_names = [
            "momentum_trend",
            "mean_reversion",
            "volatility_breakout",
            "news_sentiment",
            "pattern_recognition",
            "wyckoff_engine"
        ]

    def score_momentum_trend(self, indicators: Dict[str, float], price: float) -> Tuple[float, str, str]:
        """EMA(9) vs EMA(21) + MACD + SuperTrend + ADX Trend Strength Filter."""
        ema_9 = indicators.get("ema_9", price)
        ema_21 = indicators.get("ema_21", price)
        macd = indicators.get("macd_line", 0.0)
        adx = indicators.get("adx", 22.0)
        st_dir = indicators.get("supertrend_dir", 1.0)
        
        diff_pct = (ema_9 - ema_21) / max(1.0, ema_21)
        raw_score = diff_pct * 60.0 + (macd * 0.4) + (st_dir * 0.25)

        # ADX Trend Strength Scaling: Suppress momentum signals if ADX < 20 (choppy regime)
        adx_scale = 1.0 if adx >= 25.0 else (0.5 if adx >= 20.0 else 0.2)
        score = max(-1.0, min(1.0, raw_score * adx_scale))
        
        if score > 0.25:
            sig = "BUY"
            rationale = f"Bullish SuperTrend with EMA(9) {ema_9:.2f} > EMA(21) {ema_21:.2f} (ADX: {adx:.1f})"
        elif score < -0.25:
            sig = "SHORT"
            rationale = f"Bearish SuperTrend with EMA(9) {ema_9:.2f} < EMA(21) {ema_21:.2f} (ADX: {adx:.1f})"
        else:
            sig = "NEUTRAL"
            rationale = f"Consolidating market (ADX: {adx:.1f} < 25); momentum neutral"
        return round(score, 3), sig, rationale

    def score_mean_reversion(self, indicators: Dict[str, float], price: float) -> Tuple[float, str, str]:
        """RSI(14) + Money Flow Index (MFI) + Bollinger / Keltner Bands."""
        rsi = indicators.get("rsi_14", 50.0)
        mfi = indicators.get("mfi", 50.0)
        bb_upper = indicators.get("bb_upper", price * 1.02)
        bb_lower = indicators.get("bb_lower", price * 0.98)
        bb_width = max(0.01, bb_upper - bb_lower)
        pct_b = (price - bb_lower) / bb_width

        # Invert: oversold RSI & MFI < 35 -> bullish mean-reversion (+ score)
        # overbought RSI & MFI > 65 -> bearish mean-reversion (- score)
        score = 0.0
        if (rsi < 38.0 or pct_b < 0.15) and mfi < 40.0:
            score = max(0.3, min(1.0, (45.0 - rsi) / 25.0 + (40.0 - mfi) / 50.0))
            sig = "BUY"
            rationale = f"Dual oversold: RSI ({rsi:.1f}) & MFI ({mfi:.1f}) near lower band"
        elif (rsi > 62.0 or pct_b > 0.85) and mfi > 60.0:
            score = max(-1.0, min(-0.3, (55.0 - rsi) / 25.0 - (mfi - 60.0) / 50.0))
            sig = "SHORT"
            rationale = f"Dual overbought: RSI ({rsi:.1f}) & MFI ({mfi:.1f}) near upper band"
        else:
            sig = "NEUTRAL"
            rationale = f"RSI ({rsi:.1f}) & MFI ({mfi:.1f}) neutral within equilibrium channel"
        return round(score, 3), sig, rationale

    def score_volatility_breakout(self, indicators: Dict[str, float], price: float) -> Tuple[float, str, str]:
        """Keltner Channel & Bollinger envelope breakout with VWAP confirmation."""
        k_upper = indicators.get("keltner_upper", price * 1.02)
        k_lower = indicators.get("keltner_lower", price * 0.98)
        vwap = indicators.get("vwap", price)
        atr = indicators.get("atr", price * 0.015)
        
        if price > k_upper and price >= vwap:
            dist = (price - k_upper) / max(0.01, atr)
            score = min(1.0, 0.45 + dist * 0.35)
            sig = "BUY"
            rationale = f"Price {price:.2f} piercing Keltner Upper {k_upper:.2f} above VWAP {vwap:.2f}"
        elif price < k_lower and price <= vwap:
            dist = (k_lower - price) / max(0.01, atr)
            score = max(-1.0, -0.45 - dist * 0.35)
            sig = "SHORT"
            rationale = f"Price {price:.2f} piercing Keltner Lower {k_lower:.2f} below VWAP {vwap:.2f}"
        else:
            score = 0.0
            sig = "NEUTRAL"
            rationale = f"Price {price:.2f} oscillating within Keltner envelope ({k_lower:.2f} - {k_upper:.2f})"
        return round(score, 3), sig, rationale

    def score_news_sentiment(self, sentiment_val: float) -> Tuple[float, str, str]:
        """Finnhub / NLP sentiment index."""
        score = max(-1.0, min(1.0, sentiment_val))
        if score > 0.20:
            sig = "BUY"
            rationale = f"Positive institutional sentiment score (+{score:.2f})"
        elif score < -0.20:
            sig = "SHORT"
            rationale = f"Negative headline sentiment and risk-off score ({score:.2f})"
        else:
            sig = "NEUTRAL"
            rationale = f"Neutral market sentiment coverage ({score:+.2f})"
        return round(score, 3), sig, rationale

    def score_pattern_recognition(self, indicators: Dict[str, Any], price: float) -> Tuple[float, str, str]:
        """
        Technical Pattern Recognition Model from myhhub/stock:
        Evaluates Double Bottom (W-reversal), Double Top (M-reversal),
        Consolidation Range Breakouts, and Volume Surge factors.
        """
        score = 0.0
        signals = []
        vol_surge = float(indicators.get("volume_surge", 1.0))
        breakout = str(indicators.get("breakout_type", "NONE"))
        db_det = float(indicators.get("double_bottom_detected", 0.0)) > 0
        dt_det = float(indicators.get("double_top_detected", 0.0)) > 0

        # Double bottom bullish reversal
        if db_det:
            conf = float(indicators.get("double_bottom_conf", 0.7))
            score += 0.50 * conf
            neck = float(indicators.get("double_bottom_neckline", price))
            signals.append(f"Double Bottom pattern detected (Neckline: ${neck:.2f})")

        # Double top bearish reversal
        if dt_det:
            conf = float(indicators.get("double_top_conf", 0.7))
            score -= 0.50 * conf
            neck = float(indicators.get("double_top_neckline", price))
            signals.append(f"Double Top pattern detected (Neckline: ${neck:.2f})")

        # Range breakout
        if breakout == "BULL_BREAKOUT":
            lvl = float(indicators.get("breakout_level", price))
            score += 0.45
            signals.append(f"Bullish Range Breakout above ${lvl:.2f}")
        elif breakout == "BEAR_BREAKDOWN":
            lvl = float(indicators.get("breakout_level", price))
            score -= 0.45
            signals.append(f"Bearish Range Breakdown below ${lvl:.2f}")

        # Volume Surge confirmation booster
        if vol_surge >= 1.5:
            if score > 0:
                score = min(1.0, score * 1.3)
                signals.append(f"Volume Surge {vol_surge:.1f}x confirms bullish flow")
            elif score < 0:
                score = max(-1.0, score * 1.3)
                signals.append(f"Volume Surge {vol_surge:.1f}x confirms bearish selling")

        score = max(-1.0, min(1.0, score))
        if score >= 0.20:
            sig = "BUY"
            rat = "; ".join(signals) if signals else "Bullish pattern confirmation"
        elif score <= -0.20:
            sig = "SHORT"
            rat = "; ".join(signals) if signals else "Bearish pattern confirmation"
        else:
            sig = "NEUTRAL"
            rat = "No active reversal or breakout patterns detected"

        return round(score, 3), sig, rat

    def score_wyckoff_engine(self, indicators: Dict[str, Any], price: float) -> Tuple[float, str, str]:
        """
        Wyckoff Range Engine Model:
        Evaluates Accumulation / Distribution ranges, Phase transitions (A -> E),
        Climax events (SC/BC), Smart Springs (Phase C liquidity sweep), UTADs,
        and SOS (Sign of Strength) / SOW (Sign of Weakness) breakouts.
        """
        struct = str(indicators.get("wyckoff_structure", "NEUTRAL")).upper()
        phase = str(indicators.get("wyckoff_phase_code", "A"))
        phase_desc = str(indicators.get("wyckoff_phase", "Phase A"))
        spring_score = int(indicators.get("wyckoff_spring_score", 0))
        utad_score = int(indicators.get("wyckoff_utad_score", 0))
        climax_score = int(indicators.get("wyckoff_climax_score", 0))

        score = 0.0
        rationale_parts = []

        if "ACCUMULATION" in struct:
            if phase == "E":
                score = 0.85
                rationale_parts.append("Phase E: Active Markup trend confirmed outside range")
            elif phase == "D":
                score = 0.75
                rationale_parts.append("Phase D: Sign of Strength (SOS) range breakout")
            elif phase == "C" and spring_score >= 40:
                score = round(0.50 + (spring_score / 100.0) * 0.40, 3)
                rationale_parts.append(f"Phase C: Smart Spring liquidity sweep confirmed (Quality: {spring_score})")
            elif phase == "B":
                score = 0.20
                rationale_parts.append("Phase B: Building the cause / range absorption")
            elif climax_score >= 50:
                score = 0.35
                rationale_parts.append(f"Selling Climax (SC) effort detected (Score: {climax_score})")
        elif "DISTRIBUTION" in struct:
            if phase == "E":
                score = -0.85
                rationale_parts.append("Phase E: Active Markdown trend confirmed outside range")
            elif phase == "D":
                score = -0.75
                rationale_parts.append("Phase D: Sign of Weakness (SOW) range breakdown")
            elif phase == "C" and utad_score >= 40:
                score = -round(0.50 + (utad_score / 100.0) * 0.40, 3)
                rationale_parts.append(f"Phase C: UTAD Upthrust distribution test confirmed (Quality: {utad_score})")
            elif phase == "B":
                score = -0.20
                rationale_parts.append("Phase B: Range distribution oscillation")
            elif climax_score >= 50:
                score = -0.35
                rationale_parts.append(f"Buying Climax (BC) effort detected (Score: {climax_score})")

        score = max(-1.0, min(1.0, score))
        if score >= 0.20:
            sig = "BUY"
            rat = "; ".join(rationale_parts) if rationale_parts else f"Bullish Wyckoff structure ({phase_desc})"
        elif score <= -0.20:
            sig = "SHORT"
            rat = "; ".join(rationale_parts) if rationale_parts else f"Bearish Wyckoff structure ({phase_desc})"
        else:
            sig = "NEUTRAL"
            rat = f"Wyckoff structure in equilibrium ({phase_desc})"

        return round(score, 3), sig, rat

    def model_federation(
        self,
        indicators: Dict[str, Any],
        price: float,
        sentiment_val: float,
        current_weights: Dict[str, float],
        trend: str = "CHOPPY"
    ) -> FederationOutput:
        """
        Executes multi-model scoring, applies regime-aware dynamically calibrated weights,
        and determines consensus winner across 6 strategy models.
        """
        s_mom, sig_mom, rat_mom = self.score_momentum_trend(indicators, price)
        s_mr, sig_mr, rat_mr = self.score_mean_reversion(indicators, price)
        s_bo, sig_bo, rat_bo = self.score_volatility_breakout(indicators, price)
        s_sent, sig_sent, rat_sent = self.score_news_sentiment(sentiment_val)
        s_pat, sig_pat, rat_pat = self.score_pattern_recognition(indicators, price)
        s_wyck, sig_wyck, rat_wyck = self.score_wyckoff_engine(indicators, price)

        strat_names = [
            "momentum_trend",
            "mean_reversion",
            "volatility_breakout",
            "pattern_recognition",
            "wyckoff_engine",
            "news_sentiment"
        ]

        scores_map = {
            "momentum_trend": s_mom,
            "mean_reversion": s_mr,
            "volatility_breakout": s_bo,
            "pattern_recognition": s_pat,
            "wyckoff_engine": s_wyck,
            "news_sentiment": s_sent
        }

        # JEV Regime-Aware Strategy Calibration (6 regimes)
        if trend in ("BULL_TREND", "BEAR_TREND"):
            # Strong directional trend: momentum dominates, Wyckoff markup/markdown confirms
            regime_priors = {
                "momentum_trend": 0.35,
                "wyckoff_engine": 0.22,
                "pattern_recognition": 0.18,
                "volatility_breakout": 0.12,
                "news_sentiment": 0.08,
                "mean_reversion": 0.05
            }
        elif trend == "MEAN_REVERSION":
            # RSI extremes and range oscillations: mean reversion and Wyckoff range boundaries dominate
            regime_priors = {
                "mean_reversion": 0.35,
                "wyckoff_engine": 0.25,
                "pattern_recognition": 0.18,
                "volatility_breakout": 0.10,
                "news_sentiment": 0.07,
                "momentum_trend": 0.05
            }
        elif trend == "VOL_EXPANSION":
            # Expanding volatility: breakouts, patterns, and Wyckoff Phase D/E dominate
            regime_priors = {
                "volatility_breakout": 0.32,
                "wyckoff_engine": 0.25,
                "pattern_recognition": 0.22,
                "momentum_trend": 0.11,
                "news_sentiment": 0.06,
                "mean_reversion": 0.04
            }
        elif trend == "VOL_CONTRACTION":
            # Tight range: Wyckoff Phase C Spring/UTAD setup & Pattern breakout
            regime_priors = {
                "wyckoff_engine": 0.32,
                "pattern_recognition": 0.25,
                "mean_reversion": 0.20,
                "volatility_breakout": 0.13,
                "news_sentiment": 0.06,
                "momentum_trend": 0.04
            }
        elif trend == "CRISIS":
            # Crisis: news sentiment and anomaly detection most important
            regime_priors = {
                "news_sentiment": 0.40,
                "mean_reversion": 0.20,
                "wyckoff_engine": 0.15,
                "pattern_recognition": 0.12,
                "volatility_breakout": 0.08,
                "momentum_trend": 0.05
            }
        else:  # CHOPPY
            regime_priors = {
                "wyckoff_engine": 0.26,
                "mean_reversion": 0.26,
                "pattern_recognition": 0.20,
                "volatility_breakout": 0.12,
                "news_sentiment": 0.09,
                "momentum_trend": 0.07
            }

        # Blend regime prior with adaptive learner weights
        blended_weights = {}
        for k in strat_names:
            learner_w = current_weights.get(k, 0.17)
            prior_w = regime_priors.get(k, 0.17)
            blended_weights[k] = prior_w * 0.7 + learner_w * 0.3

        total_w = sum(blended_weights.values())
        if total_w <= 0:
            total_w = 1.0
        normalized_weights = {k: blended_weights[k] / total_w for k in strat_names}

        # Calculate weighted consensus score
        weighted_score = sum(scores_map[k] * normalized_weights[k] for k in strat_names)

        # Dominant Model Confirmation
        dominant_model = max(strat_names, key=lambda k: abs(scores_map[k]) * normalized_weights[k])
        dom_score = scores_map[dominant_model]
        if abs(dom_score) >= 0.40 and (dom_score * weighted_score >= 0):
            weighted_score = weighted_score * 0.6 + (dom_score * 0.4)

        model_details = [
            ModelSignal(name="Momentum Trend (EMA/MACD)", signal=sig_mom, score=s_mom, weight=round(normalized_weights["momentum_trend"], 3), rationale=rat_mom),
            ModelSignal(name="Mean Reversion (RSI/BB)", signal=sig_mr, score=s_mr, weight=round(normalized_weights["mean_reversion"], 3), rationale=rat_mr),
            ModelSignal(name="Volatility Breakout", signal=sig_bo, score=s_bo, weight=round(normalized_weights["volatility_breakout"], 3), rationale=rat_bo),
            ModelSignal(name="Pattern Recognition (Breakout/W-M)", signal=sig_pat, score=s_pat, weight=round(normalized_weights["pattern_recognition"], 3), rationale=rat_pat),
            ModelSignal(name="Wyckoff Range Engine (Phase/Spring)", signal=sig_wyck, score=s_wyck, weight=round(normalized_weights["wyckoff_engine"], 3), rationale=rat_wyck),
            ModelSignal(name="News Sentiment (Finnhub)", signal=sig_sent, score=s_sent, weight=round(normalized_weights["news_sentiment"], 3), rationale=rat_sent),
        ]

        # JEV Calibration: convert raw score to calibrated probability p ∈ [0,1]
        # Uses logistic mapping: p = 1 / (1 + exp(-k * score)) with k=4
        # Neutral score (0.0) → p=0.5; strong score (±0.75) → p≈0.95/0.05
        import math
        k = 4.0
        calibrated_prob = 1.0 / (1.0 + math.exp(-k * weighted_score))

        # Fractional Kelly Criterion: f = 0.25 × max(0, 2p - 1)
        # Maps p=0.50 → f=0.0 (no edge), p=0.75 → f=0.125, p=1.0 → f=0.25
        kelly_fraction = 0.25 * max(0.0, 2.0 * calibrated_prob - 1.0)

        return FederationOutput(
            outputs=scores_map,
            weights={k: round(v, 3) for k, v in normalized_weights.items()},
            federation=dominant_model,
            federated_score=round(weighted_score, 4),
            model_details=model_details,
            calibrated_prob=round(calibrated_prob, 4),
            kelly_fraction=round(kelly_fraction, 4)
        )
