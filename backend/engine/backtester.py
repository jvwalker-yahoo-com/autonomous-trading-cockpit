"""
Quantitative Backtester and Parameter Optimizer Engine.
Simulates trading sessions on historical/synthetic price series using the full
cinar/indicator quantitative pipeline (ADX, SuperTrend, VWAP, MFI, Keltner, Federation).
Performs grid search optimization to find optimal Stop-Loss, Take-Profit, and ADX filters.
"""
import time
import math
import random
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel

from .indicators import TechnicalIndicators
from .federation import FederationModule
from .models import TradeRecord

class BacktestResult(BaseModel):
    symbol: str
    starting_capital: float
    ending_equity: float
    net_pnl_usd: float
    net_pnl_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    adx_threshold: float
    trades: List[Dict[str, Any]]

class OptimizationCandidate(BaseModel):
    rank: int
    stop_loss_pct: float
    take_profit_pct: float
    adx_threshold: float
    net_pnl_pct: float
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    total_trades: int
    score: float

class OptimizationResult(BaseModel):
    symbol: str
    total_combinations_tested: int
    optimal_candidate: OptimizationCandidate
    top_candidates: List[OptimizationCandidate]
    recommendation_summary: str

class BacktesterEngine:
    def __init__(self):
        self.federation_mod = FederationModule()

    def generate_price_series(self, symbol: str, num_ticks: int = 150, base_price: float = 100.0) -> Tuple[np.ndarray, np.ndarray]:
        """Generates realistic trending/oscillating intraday price and volume series."""
        np.random.seed(abs(hash(symbol)) % 100000)
        volatility = 0.008 if symbol in ("MARA", "IREN", "SOXL", "TQQQ", "APLD") else 0.003
        
        drift = 0.0003 * np.sin(np.linspace(0, 3 * np.pi, num_ticks))
        returns = np.random.normal(drift, volatility, num_ticks)
        prices = base_price * np.cumprod(1.0 + returns)
        volumes = np.random.uniform(50000, 350000, num_ticks)
        return prices, volumes

    def run_backtest(
        self,
        symbol: str,
        initial_capital: float = 10000.0,
        stop_loss_pct: float = 0.025,
        take_profit_pct: float = 0.050,
        adx_threshold: float = 20.0,
        num_ticks: int = 150,
        base_price: float = 100.0,
        provided_prices: Optional[np.ndarray] = None,
        provided_volumes: Optional[np.ndarray] = None
    ) -> BacktestResult:
        """
        Executes an end-to-end backtest on a price series.
        """
        if provided_prices is not None and len(provided_prices) > 20:
            prices = provided_prices
            volumes = provided_volumes if provided_volumes is not None else np.ones(len(prices)) * 100000
        else:
            prices, volumes = self.generate_price_series(symbol, num_ticks, base_price)

        cash = initial_capital
        equity = initial_capital
        peak_equity = initial_capital
        max_drawdown = 0.0

        open_position: Optional[Dict[str, Any]] = None
        trades: List[Dict[str, Any]] = []
        weights = {"momentum_trend": 0.35, "mean_reversion": 0.20, "volatility_breakout": 0.35, "news_sentiment": 0.10}

        for i in range(25, len(prices)):
            curr_p = float(prices[i])
            curr_slice = prices[:i+1]
            vol_slice = volumes[:i+1]
            highs = curr_slice * 1.004
            lows = curr_slice * 0.996

            # Compute technical indicators
            ema_9 = TechnicalIndicators.calc_ema(curr_slice, 9)
            ema_21 = TechnicalIndicators.calc_ema(curr_slice, 21)
            ema_12 = TechnicalIndicators.calc_ema(curr_slice, 12)
            ema_26 = TechnicalIndicators.calc_ema(curr_slice, 26)
            macd_line = ema_12 - ema_26

            deltas = np.diff(curr_slice[-15:])
            gains = np.where(deltas > 0, deltas, 0.0)
            losses = np.where(deltas < 0, -deltas, 0.0)
            avg_gain = np.mean(gains) if len(gains) > 0 else 0.001
            avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
            rsi = 100.0 - (100.0 / (1.0 + (avg_gain / max(0.0001, avg_loss))))

            window = curr_slice[-20:]
            bb_mid = float(np.mean(window))
            std = float(np.std(window))
            bb_upper = bb_mid + (2.0 * std)
            bb_lower = bb_mid - (2.0 * std)

            atr = TechnicalIndicators.calc_atr(highs, lows, curr_slice, 14)
            adx, _, _ = TechnicalIndicators.calc_adx(highs, lows, curr_slice, 14)
            st_val, st_dir = TechnicalIndicators.calc_supertrend(highs, lows, curr_slice, 10, 3.0)
            vwap = TechnicalIndicators.calc_vwap(curr_slice, vol_slice)
            mfi = TechnicalIndicators.calc_mfi(highs, lows, curr_slice, vol_slice, 14)
            k_upper, k_mid, k_lower = TechnicalIndicators.calc_keltner_channel(highs, lows, curr_slice, 20, 10, 2.0)

            indicators = {
                "ema_9": ema_9, "ema_21": ema_21, "rsi_14": rsi, "macd_line": macd_line,
                "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid, "atr": atr,
                "adx": adx, "supertrend_val": st_val, "supertrend_dir": float(st_dir),
                "vwap": vwap, "mfi": mfi, "keltner_upper": k_upper, "keltner_mid": k_mid, "keltner_lower": k_lower
            }

            # Check open position Stop-Loss and Take-Profit
            if open_position is not None:
                is_long = open_position["direction"] == "LONG"
                entry_p = open_position["entry_price"]
                shares = open_position["shares"]
                sl_p = open_position["stop_loss"]
                tp_p = open_position["take_profit"]

                closed = False
                exit_rationale = ""

                if is_long:
                    if curr_p <= sl_p:
                        closed = True
                        exit_rationale = f"Stop-Loss hit at ${curr_p:.2f} (Target SL: ${sl_p:.2f})"
                    elif curr_p >= tp_p:
                        closed = True
                        exit_rationale = f"Take-Profit hit at ${curr_p:.2f} (Target TP: ${tp_p:.2f})"
                else: # SHORT
                    if curr_p >= sl_p:
                        closed = True
                        exit_rationale = f"Stop-Loss hit on SHORT at ${curr_p:.2f} (Target SL: ${sl_p:.2f})"
                    elif curr_p <= tp_p:
                        closed = True
                        exit_rationale = f"Take-Profit hit on SHORT at ${curr_p:.2f} (Target TP: ${tp_p:.2f})"

                if closed:
                    pnl_usd = (curr_p - entry_p) * shares if is_long else (entry_p - curr_p) * shares
                    pnl_pct = (pnl_usd / (entry_p * shares)) * 100.0
                    cash += (open_position["cost_basis"] + pnl_usd)
                    trades.append({
                        "symbol": symbol,
                        "direction": open_position["direction"],
                        "shares": round(shares, 4),
                        "entry_price": round(entry_p, 2),
                        "exit_price": round(curr_p, 2),
                        "realized_pnl_usd": round(pnl_usd, 2),
                        "realized_pnl_pct": round(pnl_pct, 2),
                        "win": pnl_usd > 0,
                        "entry_time": f"Tick {open_position['tick_index']}",
                        "exit_time": f"Tick {i}",
                        "rationale": f"{open_position['rationale']} | {exit_rationale}"
                    })
                    open_position = None

            # Calculate current total equity
            unrealized = 0.0
            if open_position is not None:
                is_long = open_position["direction"] == "LONG"
                unrealized = (curr_p - open_position["entry_price"]) * open_position["shares"] if is_long else (open_position["entry_price"] - curr_p) * open_position["shares"]
            equity = cash + (open_position["cost_basis"] if open_position else 0.0) + unrealized
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity
            if dd > max_drawdown:
                max_drawdown = dd

            # Signal evaluation for new entry
            if open_position is None and adx >= adx_threshold:
                fed_out = self.federation_mod.model_federation(indicators, curr_p, 0.05, weights)
                score = fed_out.federated_score

                if score >= 0.28: # BUY LONG
                    alloc = min(1000.0, cash * 0.25)
                    if alloc >= 50.0:
                        sh = round(alloc / curr_p, 4)
                        cost = sh * curr_p
                        cash -= cost
                        open_position = {
                            "direction": "LONG",
                            "shares": sh,
                            "entry_price": curr_p,
                            "cost_basis": cost,
                            "stop_loss": round(curr_p * (1.0 - stop_loss_pct), 2),
                            "take_profit": round(curr_p * (1.0 + take_profit_pct), 2),
                            "tick_index": i,
                            "rationale": f"Long entry on {symbol} (Ensemble: {score:+.2f}, ADX: {adx:.1f})"
                        }
                elif score <= -0.28: # SHORT CFD
                    alloc = min(1000.0, cash * 0.25)
                    if alloc >= 50.0:
                        sh = round(alloc / curr_p, 4)
                        cost = sh * curr_p
                        cash -= cost
                        open_position = {
                            "direction": "SHORT",
                            "shares": sh,
                            "entry_price": curr_p,
                            "cost_basis": cost,
                            "stop_loss": round(curr_p * (1.0 + stop_loss_pct), 2),
                            "take_profit": round(curr_p * (1.0 - take_profit_pct), 2),
                            "tick_index": i,
                            "rationale": f"Short entry on {symbol} (Ensemble: {score:+.2f}, ADX: {adx:.1f})"
                        }

        # Close open position at the end of session
        if open_position is not None:
            last_p = float(prices[-1])
            is_long = open_position["direction"] == "LONG"
            pnl_usd = (last_p - open_position["entry_price"]) * open_position["shares"] if is_long else (open_position["entry_price"] - last_p) * open_position["shares"]
            pnl_pct = (pnl_usd / open_position["cost_basis"]) * 100.0
            cash += (open_position["cost_basis"] + pnl_usd)
            trades.append({
                "symbol": symbol,
                "direction": open_position["direction"],
                "shares": round(open_position["shares"], 4),
                "entry_price": round(open_position["entry_price"], 2),
                "exit_price": round(last_p, 2),
                "realized_pnl_usd": round(pnl_usd, 2),
                "realized_pnl_pct": round(pnl_pct, 2),
                "win": pnl_usd > 0,
                "entry_time": f"Tick {open_position['tick_index']}",
                "exit_time": f"Tick {len(prices)-1}",
                "rationale": f"{open_position['rationale']} | Session close settlement"
            })
            open_position = None

        final_equity = cash
        net_pnl = final_equity - initial_capital
        net_pnl_pct = (net_pnl / initial_capital) * 100.0

        winning_trades = sum(1 for t in trades if t["win"])
        losing_trades = sum(1 for t in trades if not t["win"])
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_wins = sum(t["realized_pnl_usd"] for t in trades if t["win"])
        gross_losses = abs(sum(t["realized_pnl_usd"] for t in trades if not t["win"]))
        profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else (gross_wins if gross_wins > 0 else 1.0)

        return BacktestResult(
            symbol=symbol,
            starting_capital=initial_capital,
            ending_equity=round(final_equity, 2),
            net_pnl_usd=round(net_pnl, 2),
            net_pnl_pct=round(net_pnl_pct, 2),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(max_drawdown * 100.0, 2),
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            adx_threshold=adx_threshold,
            trades=trades
        )

    def optimize_parameters(
        self,
        symbol: str,
        initial_capital: float = 10000.0,
        base_price: float = 100.0
    ) -> OptimizationResult:
        """
        Runs grid search parameter optimization across Stop-Loss, Take-Profit, and ADX filters.
        """
        prices, volumes = self.generate_price_series(symbol, 180, base_price)

        sl_candidates = [0.015, 0.025, 0.035, 0.045]
        tp_candidates = [0.030, 0.050, 0.070, 0.090]
        adx_candidates = [18.0, 22.0, 26.0]

        results: List[OptimizationCandidate] = []

        for sl in sl_candidates:
            for tp in tp_candidates:
                for adx in adx_candidates:
                    res = self.run_backtest(
                        symbol=symbol,
                        initial_capital=initial_capital,
                        stop_loss_pct=sl,
                        take_profit_pct=tp,
                        adx_threshold=adx,
                        provided_prices=prices,
                        provided_volumes=volumes
                    )
                    
                    # Fitness score: balances Return, Profit Factor, Win Rate, and penalizes Drawdown
                    score = (res.net_pnl_pct * 2.0) + (res.win_rate_pct * 0.5) + (res.profit_factor * 10.0) - (res.max_drawdown_pct * 3.0)
                    
                    results.append(OptimizationCandidate(
                        rank=0,
                        stop_loss_pct=sl,
                        take_profit_pct=tp,
                        adx_threshold=adx,
                        net_pnl_pct=res.net_pnl_pct,
                        win_rate_pct=res.win_rate_pct,
                        profit_factor=res.profit_factor,
                        max_drawdown_pct=res.max_drawdown_pct,
                        total_trades=res.total_trades,
                        score=round(score, 2)
                    ))

        # Sort by fitness score descending
        results.sort(key=lambda x: x.score, reverse=True)
        for i, c in enumerate(results):
            c.rank = i + 1

        optimal = results[0]
        summary = f"Optimal configuration for {symbol}: Stop-Loss {(optimal.stop_loss_pct*100):.1f}%, Take-Profit {(optimal.take_profit_pct*100):.1f}%, ADX filter {optimal.adx_threshold:.0f} (Yields {optimal.win_rate_pct:.1f}% Win Rate, {optimal.profit_factor:.2f} Profit Factor, +{optimal.net_pnl_pct:.2f}% Return)."

        return OptimizationResult(
            symbol=symbol,
            total_combinations_tested=len(results),
            optimal_candidate=optimal,
            top_candidates=results[:5],
            recommendation_summary=summary
        )
