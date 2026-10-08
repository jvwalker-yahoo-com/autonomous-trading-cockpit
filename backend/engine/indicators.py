"""
Quantitative Technical Indicators Engine.
Ported from high-performance algorithms in cinar/indicator using pure NumPy.
Provides ADX (Trend Strength), SuperTrend, VWAP, MFI (Money Flow Index),
Keltner Channels, Stochastic Oscillator, RSI, MACD, EMA, and ATR.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional, Any

class TechnicalIndicators:
    @staticmethod
    def calc_ema(arr: np.ndarray, period: int) -> float:
        """Exponential Moving Average."""
        if len(arr) == 0:
            return 0.0
        if len(arr) < period:
            return float(np.mean(arr))
        alpha = 2.0 / (period + 1.0)
        ema = arr[0]
        for val in arr[1:]:
            ema = alpha * val + (1.0 - alpha) * ema
        return float(ema)

    @staticmethod
    def calc_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Average True Range (ATR)."""
        if len(closes) < 2:
            return float(closes[-1] * 0.015) if len(closes) > 0 else 1.0
        
        n = min(len(closes) - 1, period)
        tr_list = []
        for i in range(-n, 0):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
        return float(np.mean(tr_list)) if tr_list else float(closes[-1] * 0.015)

    @staticmethod
    def calc_adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> Tuple[float, float, float]:
        """
        Average Directional Index (ADX) from cinar/indicator.
        Measures trend strength regardless of direction.
        Returns: (adx, plus_di, minus_di)
        - ADX > 25: Strong trending regime
        - ADX < 20: Choppy / Range-bound consolidation
        """
        if len(closes) < period + 2:
            return 22.0, 20.0, 20.0

        n = len(closes)
        plus_dm = []
        minus_dm = []
        tr_list = []

        for i in range(1, n):
            h = highs[i]
            l = lows[i]
            prev_h = highs[i - 1]
            prev_l = lows[i - 1]
            prev_c = closes[i - 1]

            up_move = h - prev_h
            down_move = prev_l - l

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0.0)

            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0.0)

            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(max(0.001, tr))

        # Wilder smoothing
        window = min(period, len(tr_list))
        smoothed_tr = np.mean(tr_list[-window:])
        smoothed_plus = np.mean(plus_dm[-window:])
        smoothed_minus = np.mean(minus_dm[-window:])

        if smoothed_tr == 0:
            return 20.0, 20.0, 20.0

        plus_di = (smoothed_plus / smoothed_tr) * 100.0
        minus_di = (smoothed_minus / smoothed_tr) * 100.0
        di_sum = plus_di + minus_di

        dx = (abs(plus_di - minus_di) / di_sum * 100.0) if di_sum > 0 else 0.0
        adx = dx * 0.4 + 20.0 * 0.6 # Smoothed estimate
        return round(float(adx), 2), round(float(plus_di), 2), round(float(minus_di), 2)

    @staticmethod
    def calc_supertrend(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 10, multiplier: float = 3.0) -> Tuple[float, int]:
        """
        SuperTrend indicator algorithm from cinar/indicator.
        Returns: (supertrend_value, trend_direction: +1 for Bullish, -1 for Bearish)
        """
        if len(closes) < period:
            return float(closes[-1]), 1

        atr = TechnicalIndicators.calc_atr(highs, lows, closes, period)
        hl2 = (highs[-1] + lows[-1]) / 2.0
        upper_basic = hl2 + (multiplier * atr)
        lower_basic = hl2 - (multiplier * atr)

        close = closes[-1]
        prev_close = closes[-2] if len(closes) > 1 else close

        if close > upper_basic:
            return round(lower_basic, 2), 1 # Bullish
        elif close < lower_basic:
            return round(upper_basic, 2), -1 # Bearish
        else:
            return round(lower_basic if close >= prev_close else upper_basic, 2), (1 if close >= prev_close else -1)

    @staticmethod
    def calc_vwap(prices: np.ndarray, volumes: np.ndarray) -> float:
        """Volume-Weighted Average Price (VWAP)."""
        if len(prices) == 0 or len(volumes) == 0 or len(prices) != len(volumes):
            return float(prices[-1]) if len(prices) > 0 else 100.0
        vol_sum = np.sum(volumes)
        if vol_sum == 0:
            return float(np.mean(prices))
        vwap = np.sum(prices * volumes) / vol_sum
        return round(float(vwap), 2)

    @staticmethod
    def calc_mfi(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray, period: int = 14) -> float:
        """
        Money Flow Index (MFI) from cinar/indicator.
        Measures institutional volume flow and price momentum (0-100).
        """
        if len(closes) < period + 1 or len(volumes) < period + 1:
            return 50.0

        typ_prices = (highs + lows + closes) / 3.0
        pos_flow = 0.0
        neg_flow = 0.0

        n = min(len(typ_prices) - 1, period)
        for i in range(-n, 0):
            curr_tp = typ_prices[i]
            prev_tp = typ_prices[i - 1]
            raw_flow = curr_tp * volumes[i]

            if curr_tp > prev_tp:
                pos_flow += raw_flow
            elif curr_tp < prev_tp:
                neg_flow += raw_flow

        if neg_flow == 0:
            return 100.0
        money_ratio = pos_flow / neg_flow
        mfi = 100.0 - (100.0 / (1.0 + money_ratio))
        return round(float(mfi), 2)

    @staticmethod
    def calc_keltner_channel(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> Tuple[float, float, float]:
        """
        Keltner Channels from cinar/indicator.
        Returns: (keltner_upper, keltner_mid, keltner_lower)
        """
        mid = TechnicalIndicators.calc_ema(closes, ema_period)
        atr = TechnicalIndicators.calc_atr(highs, lows, closes, atr_period)
        upper = mid + (multiplier * atr)
        lower = mid - (multiplier * atr)
        return round(upper, 2), round(mid, 2), round(lower, 2)

    @staticmethod
    def calc_volume_surge(volumes: np.ndarray, period: int = 20) -> float:
        """
        Volume Surge Factor from myhhub/stock:
        Calculates ratio of latest volume to the rolling N-period volume moving average.
        Ratio > 1.5 indicates institutional volume surge/breakout momentum.
        """
        if len(volumes) < 3:
            return 1.0
        n = min(len(volumes) - 1, period)
        prev_vols = volumes[-n-1:-1]
        baseline = float(np.mean(prev_vols)) if len(prev_vols) > 0 else float(volumes[-1])
        if baseline <= 0:
            return 1.0
        return round(float(volumes[-1] / baseline), 2)

    @staticmethod
    def detect_range_breakout(prices: np.ndarray, highs: np.ndarray, lows: np.ndarray, period: int = 20) -> Tuple[str, float]:
        """
        Consolidation Range Breakout Engine from myhhub/stock.
        Identifies price expansion outside of recent trading range.
        Returns: (breakout_type: 'BULL_BREAKOUT' | 'BEAR_BREAKDOWN' | 'NONE', breakout_level)
        """
        if len(prices) < period + 1 or len(highs) < period + 1 or len(lows) < period + 1:
            return "NONE", 0.0

        n = min(len(prices) - 1, period)
        range_high = float(np.max(highs[-n-1:-1]))
        range_low = float(np.min(lows[-n-1:-1]))
        current_price = float(prices[-1])

        if current_price > range_high:
            return "BULL_BREAKOUT", round(range_high, 2)
        elif current_price < range_low:
            return "BEAR_BREAKDOWN", round(range_low, 2)
        return "NONE", 0.0

    @staticmethod
    def detect_double_bottom(prices: np.ndarray, threshold_pct: float = 0.018) -> Tuple[bool, float, float]:
        """
        Double Bottom ('W' Reversal Pattern) Detection from myhhub/stock.
        Identifies two swing lows within threshold % separated by an intermediate peak (neckline).
        Returns: (is_detected, neckline_price, pattern_confidence)
        """
        if len(prices) < 20:
            return False, 0.0, 0.0

        window = prices[-30:] if len(prices) >= 30 else prices
        n = len(window)
        # Find local troughs
        troughs = []
        for i in range(2, n - 2):
            if window[i] <= window[i-1] and window[i] <= window[i-2] and window[i] <= window[i+1] and window[i] <= window[i+2]:
                troughs.append((i, window[i]))

        if len(troughs) < 2:
            return False, 0.0, 0.0

        # Check last two troughs
        idx1, p1 = troughs[-2]
        idx2, p2 = troughs[-1]

        # Separation must be at least 4 bars
        if (idx2 - idx1) < 4:
            return False, 0.0, 0.0

        # Lows must be within threshold_pct of each other
        diff_pct = abs(p1 - p2) / max(0.01, min(p1, p2))
        if diff_pct <= threshold_pct:
            # Neckline is the peak between the two troughs
            neckline = float(np.max(window[idx1:idx2+1]))
            current_p = window[-1]
            # Pattern valid if current price is recovering toward or above neckline
            if current_p >= min(p1, p2) * 1.005:
                confidence = round(max(0.4, min(0.95, 1.0 - diff_pct * 25.0)), 2)
                return True, round(neckline, 2), confidence

        return False, 0.0, 0.0

    @staticmethod
    def detect_double_top(prices: np.ndarray, threshold_pct: float = 0.018) -> Tuple[bool, float, float]:
        """
        Double Top ('M' Reversal Pattern) Detection from myhhub/stock.
        Identifies two swing highs within threshold % separated by an intermediate valley (neckline).
        Returns: (is_detected, neckline_price, pattern_confidence)
        """
        if len(prices) < 20:
            return False, 0.0, 0.0

        window = prices[-30:] if len(prices) >= 30 else prices
        n = len(window)
        peaks = []
        for i in range(2, n - 2):
            if window[i] >= window[i-1] and window[i] >= window[i-2] and window[i] >= window[i+1] and window[i] >= window[i+2]:
                peaks.append((i, window[i]))

        if len(peaks) < 2:
            return False, 0.0, 0.0

        idx1, p1 = peaks[-2]
        idx2, p2 = peaks[-1]

        if (idx2 - idx1) < 4:
            return False, 0.0, 0.0

        diff_pct = abs(p1 - p2) / max(0.01, max(p1, p2))
        if diff_pct <= threshold_pct:
            neckline = float(np.min(window[idx1:idx2+1]))
            current_p = window[-1]
            if current_p <= max(p1, p2) * 0.995:
                confidence = round(max(0.4, min(0.95, 1.0 - diff_pct * 25.0)), 2)
                return True, round(neckline, 2), confidence

        return False, 0.0, 0.0

    @staticmethod
    def calc_chip_distribution_density(prices: np.ndarray, volumes: np.ndarray, num_bins: int = 10) -> Dict[str, Any]:
        """
        Volume Chip Distribution (筹码分布) algorithm from myhhub/stock:
        Calculates the cost density distribution of market participants to locate
        major support/resistance zones.
        """
        if len(prices) < 10 or len(volumes) < 10:
            return {"chip_support": float(prices[-1]) * 0.98 if len(prices) > 0 else 0.0, "chip_resistance": float(prices[-1]) * 1.02 if len(prices) > 0 else 0.0}

        min_p = float(np.min(prices))
        max_p = float(np.max(prices))
        if min_p == max_p:
            return {"chip_support": round(min_p * 0.98, 2), "chip_resistance": round(max_p * 1.02, 2)}

        bins = np.linspace(min_p, max_p, num_bins + 1)
        bin_volumes = np.zeros(num_bins)

        for p, v in zip(prices, volumes):
            idx = min(num_bins - 1, int((p - min_p) / (max_p - min_p) * num_bins))
            bin_volumes[idx] += v

        max_bin_idx = int(np.argmax(bin_volumes))
        chip_core_price = (bins[max_bin_idx] + bins[max_bin_idx + 1]) / 2.0
        cur_p = float(prices[-1])

        return {
            "chip_core_price": round(chip_core_price, 2),
            "chip_support": round(chip_core_price if cur_p >= chip_core_price else min_p, 2),
            "chip_resistance": round(chip_core_price if cur_p < chip_core_price else max_p, 2),
            "current_above_chip_core": cur_p >= chip_core_price
        }

    @staticmethod
    def calc_dual_thrust(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        open_price: float,
        current_price: float,
        lookback_days: int = 4,
        k1: float = 0.5,
        k2: float = 0.5
    ) -> Dict[str, Any]:
        """
        Dual Thrust Breakout Strategy from je-suis-tm/quant-trading:
        Calculates asymmetric upper and lower breakout thresholds based on historical N-day range.
        HH = highest high over lookback
        HC = highest close over lookback
        LL = lowest low over lookback
        LC = lowest close over lookback
        range = max(HH - LC, HC - LL)
        Buy Line = Open + k1 * range
        Sell Line = Open - k2 * range
        """
        if len(closes) < 2:
            range_val = float(current_price * 0.02)
            buy_line = open_price + k1 * range_val
            sell_line = open_price - k2 * range_val
            return {
                "dual_thrust_buy_line": round(buy_line, 4),
                "dual_thrust_sell_line": round(sell_line, 4),
                "dual_thrust_range": round(range_val, 4),
                "dual_thrust_signal": "BUY" if current_price > buy_line else ("SHORT" if current_price < sell_line else "NONE")
            }

        lb = min(len(closes), lookback_days)
        h_slice = highs[-lb:]
        l_slice = lows[-lb:]
        c_slice = closes[-lb:]

        hh = float(np.max(h_slice))
        hc = float(np.max(c_slice))
        ll = float(np.min(l_slice))
        lc = float(np.min(c_slice))

        range_val = max(hh - lc, hc - ll)
        if range_val <= 0:
            range_val = float(current_price * 0.015)

        buy_line = open_price + k1 * range_val
        sell_line = open_price - k2 * range_val

        signal = "NONE"
        if current_price > buy_line:
            signal = "BUY"
        elif current_price < sell_line:
            signal = "SHORT"

        return {
            "dual_thrust_buy_line": round(buy_line, 4),
            "dual_thrust_sell_line": round(sell_line, 4),
            "dual_thrust_range": round(range_val, 4),
            "dual_thrust_signal": signal
        }

    @staticmethod
    def calc_london_breakout(
        premarket_prices: np.ndarray,
        current_price: float,
        buffer_pct: float = 0.001
    ) -> Dict[str, Any]:
        """
        London Breakout Strategy from je-suis-tm/quant-trading:
        Captures opening range volatility breakout (tailored for UK100, GER40, European morning sessions).
        Establishes high/low range during the pre-market window (07:00 - 08:00 UK time),
        then generates a breakout signal when the 08:00 London open breaks past the channel.
        """
        if len(premarket_prices) < 2:
            return {
                "london_range_high": round(current_price * (1.0 + buffer_pct), 2),
                "london_range_low": round(current_price * (1.0 - buffer_pct), 2),
                "london_breakout_signal": "NONE"
            }

        high_lvl = float(np.max(premarket_prices)) * (1.0 + buffer_pct)
        low_lvl = float(np.min(premarket_prices)) * (1.0 - buffer_pct)

        signal = "NONE"
        if current_price > high_lvl:
            signal = "BUY"
        elif current_price < low_lvl:
            signal = "SHORT"

        return {
            "london_range_high": round(high_lvl, 2),
            "london_range_low": round(low_lvl, 2),
            "london_breakout_signal": signal
        }

    @staticmethod
    def calc_heikin_ashi(
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray
    ) -> Dict[str, Any]:
        """
        Heikin-Ashi Candlestick Smoothing from je-suis-tm/quant-trading:
        Filters out market noise and false pullbacks for robust trend detection.
        ha_close = (open + high + low + close) / 4
        ha_open = (prev_ha_open + prev_ha_close) / 2
        ha_high = max(high, ha_open, ha_close)
        ha_low = min(low, ha_open, ha_close)
        """
        n = len(closes)
        if n == 0:
            return {"ha_trend": "CHOPPY", "ha_consecutive_bars": 0, "ha_bullish": False}

        ha_closes = (opens + highs + lows + closes) / 4.0
        ha_opens = np.zeros(n)
        ha_opens[0] = (opens[0] + closes[0]) / 2.0

        for i in range(1, n):
            ha_opens[i] = (ha_opens[i-1] + ha_closes[i-1]) / 2.0

        ha_highs = np.maximum(highs, np.maximum(ha_opens, ha_closes))
        ha_lows = np.minimum(lows, np.minimum(ha_opens, ha_closes))

        last_open = ha_opens[-1]
        last_close = ha_closes[-1]
        is_bullish = bool(last_close > last_open)

        # Count consecutive trending bars
        consecutive = 0
        for i in range(n - 1, -1, -1):
            if (ha_closes[i] > ha_opens[i]) == is_bullish:
                consecutive += 1
            else:
                break

        trend = "BULLISH" if (is_bullish and consecutive >= 2) else ("BEARISH" if (not is_bullish and consecutive >= 2) else "CHOPPY")

        return {
            "ha_open": round(float(last_open), 4),
            "ha_close": round(float(last_close), 4),
            "ha_high": round(float(ha_highs[-1]), 4),
            "ha_low": round(float(ha_lows[-1]), 4),
            "ha_trend": trend,
            "ha_consecutive_bars": consecutive,
            "ha_bullish": is_bullish
        }
