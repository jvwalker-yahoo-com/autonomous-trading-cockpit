"""
Broker simulation module with fractional share execution (eToro model),
Long/Short position management, automated Stop-Loss / Take-Profit enforcement,
and persistent ledger storage.
"""
import json
import uuid
import os
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from .models import Position, TradeRecord, PortfolioSummary, StockPerformanceSummary, MultiDayPerformanceReport
from .learner import AdaptiveLearner

class SimulatedBroker:
    def __init__(self, initial_capital: float = 10000.0, db_path: str = "", learner: Optional[AdaptiveLearner] = None):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trade_ledger: List[TradeRecord] = []
        self.db_path = db_path
        self.learner = learner or AdaptiveLearner()
        self.peak_equity = initial_capital
        
        # Load persisted state if exists
        self.load_state()

    def get_equity(self) -> float:
        """Returns total portfolio equity = Cash + Total Market Value of Positions."""
        equity = self.cash
        for pos in self.positions.values():
            equity += pos.market_value_usd
        return round(equity, 2)

    def get_portfolio_summary(self, active_symbol: str = "AAPL", simulation_mode: bool = True) -> PortfolioSummary:
        equity = self.get_equity()
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        drawdown_pct = max(0.0, (self.peak_equity - equity) / max(1.0, self.peak_equity))
        
        wins = [t for t in self.trade_ledger if t.win]
        losses = [t for t in self.trade_ledger if not t.win]
        total_pnl = sum(t.realized_pnl_usd for t in self.trade_ledger)
        total_pnl_pct = (total_pnl / self.initial_capital) * 100.0
        
        win_rate = (len(wins) / max(1, len(self.trade_ledger))) * 100.0
        tot_win_usd = sum(t.realized_pnl_usd for t in wins)
        tot_loss_usd = sum(abs(t.realized_pnl_usd) for t in losses)
        profit_factor = (tot_win_usd / max(0.01, tot_loss_usd)) if tot_loss_usd > 0 else (tot_win_usd or 1.0)
        
        unrealized = sum(p.unrealized_pnl_usd for p in self.positions.values())

        return PortfolioSummary(
            cash=round(self.cash, 2),
            equity=round(equity, 2),
            initial_capital=self.initial_capital,
            total_realized_pnl_usd=round(total_pnl, 2),
            total_realized_pnl_pct=round(total_pnl_pct, 2),
            unrealized_pnl_usd=round(unrealized, 2),
            win_count=len(wins),
            loss_count=len(losses),
            total_trades=len(self.trade_ledger),
            win_rate_pct=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(drawdown_pct * 100.0, 2),
            open_positions=list(self.positions.values()),
            active_symbol=active_symbol,
            simulation_mode=simulation_mode
        )

    def execute_order(
        self,
        symbol: str,
        direction: str, # "LONG" or "SHORT"
        allocated_usd: float,
        current_price: float,
        stop_loss_pct: float = 0.025,
        take_profit_pct: float = 0.050,
        rationale: str = "",
        contributing_models: Optional[Dict[str, float]] = None
    ) -> Optional[Position]:
        """
        Executes a fractional share market order (Long or Short CFD).
        """
        if allocated_usd > self.cash:
            allocated_usd = self.cash * 0.95 # Cap to available cash
            
        if allocated_usd < 20.0 or current_price <= 0:
            return None

        # Check if already holding opposite position on this symbol
        if symbol in self.positions:
            existing = self.positions[symbol]
            if existing.direction != direction:
                # Close existing opposite position first
                self.close_position(symbol, current_price, exit_rationale="Opposite signal reversal")
            else:
                return existing # Already in same direction

        # Apply spread / execution cost (eToro model: ~0.05%)
        effective_price = current_price * 1.0005 if direction == "LONG" else current_price * 0.9995
        fractional_shares = round(allocated_usd / effective_price, 4)
        cost_basis = round(fractional_shares * effective_price, 2)

        self.cash = round(self.cash - cost_basis, 2)

        # Compute SL & TP levels
        if direction == "LONG":
            sl_price = round(effective_price * (1.0 - stop_loss_pct), 2)
            tp_price = round(effective_price * (1.0 + take_profit_pct), 2)
        else: # SHORT
            sl_price = round(effective_price * (1.0 + stop_loss_pct), 2)
            tp_price = round(effective_price * (1.0 - take_profit_pct), 2)

        pos_id = f"pos_{uuid.uuid4().hex[:8]}"
        position = Position(
            id=pos_id,
            symbol=symbol,
            direction=direction,
            shares=fractional_shares,
            entry_price=round(effective_price, 2),
            current_price=round(current_price, 2),
            cost_basis_usd=cost_basis,
            market_value_usd=cost_basis,
            unrealized_pnl_usd=0.0,
            unrealized_pnl_pct=0.0,
            stop_loss=sl_price,
            take_profit=tp_price,
            entry_time=datetime.now(timezone.utc).isoformat(),
            rationale=rationale,
            contributing_models=contributing_models or {}
        )

        self.positions[symbol] = position
        self.save_state()
        return position

    def update_price_and_check_stops(self, symbol: str, current_price: float) -> List[TradeRecord]:
        """
        Updates live position valuation and checks Stop-Loss / Take-Profit triggers.
        """
        closed_trades = []
        if symbol not in self.positions:
            return closed_trades

        pos = self.positions[symbol]
        pos.current_price = round(current_price, 2)

        if pos.direction == "LONG":
            pos.market_value_usd = round(pos.shares * current_price, 2)
            pos.unrealized_pnl_usd = round(pos.market_value_usd - pos.cost_basis_usd, 2)
            pos.unrealized_pnl_pct = round((pos.unrealized_pnl_usd / pos.cost_basis_usd) * 100.0, 2)

            # Check SL / TP
            if current_price <= pos.stop_loss:
                trade = self.close_position(symbol, current_price, exit_rationale=f"Stop-Loss hit at {current_price:.2f} (Target SL: {pos.stop_loss:.2f})")
                if trade: closed_trades.append(trade)
            elif current_price >= pos.take_profit:
                trade = self.close_position(symbol, current_price, exit_rationale=f"Take-Profit hit at {current_price:.2f} (Target TP: {pos.take_profit:.2f})")
                if trade: closed_trades.append(trade)

        else: # SHORT
            pnl = (pos.entry_price - current_price) * pos.shares
            pos.market_value_usd = round(pos.cost_basis_usd + pnl, 2)
            pos.unrealized_pnl_usd = round(pnl, 2)
            pos.unrealized_pnl_pct = round((pos.unrealized_pnl_usd / pos.cost_basis_usd) * 100.0, 2)

            # Check SL / TP for Short
            if current_price >= pos.stop_loss:
                trade = self.close_position(symbol, current_price, exit_rationale=f"Stop-Loss hit on SHORT at {current_price:.2f} (Target SL: {pos.stop_loss:.2f})")
                if trade: closed_trades.append(trade)
            elif current_price <= pos.take_profit:
                trade = self.close_position(symbol, current_price, exit_rationale=f"Take-Profit hit on SHORT at {current_price:.2f} (Target TP: {pos.take_profit:.2f})")
                if trade: closed_trades.append(trade)

        return closed_trades

    def close_position(self, symbol: str, current_price: float, exit_rationale: str = "Manual / System exit", contributing_models: Optional[Dict[str, float]] = None) -> Optional[TradeRecord]:
        """
        Closes position, updates cash balance, records trade ledger,
        and feeds trade outcome to the Adaptive Learner.
        """
        if symbol not in self.positions:
            return None

        pos = self.positions.pop(symbol)
        
        if pos.direction == "LONG":
            exit_value = round(pos.shares * current_price, 2)
            realized_pnl = round(exit_value - pos.cost_basis_usd, 2)
        else: # SHORT
            pnl = (pos.entry_price - current_price) * pos.shares
            exit_value = round(pos.cost_basis_usd + pnl, 2)
            realized_pnl = round(pnl, 2)

        self.cash = round(self.cash + exit_value, 2)
        realized_pct = round((realized_pnl / pos.cost_basis_usd) * 100.0, 2)
        is_win = realized_pnl > 0.0

        resolved_models = contributing_models if contributing_models is not None else pos.contributing_models

        trade_record = TradeRecord(
            id=f"tr_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            direction=pos.direction,
            shares=pos.shares,
            entry_price=pos.entry_price,
            exit_price=round(current_price, 2),
            cost_basis_usd=pos.cost_basis_usd,
            exit_value_usd=exit_value,
            realized_pnl_usd=realized_pnl,
            realized_pnl_pct=realized_pct,
            win=is_win,
            entry_time=pos.entry_time,
            exit_time=datetime.now(timezone.utc).isoformat(),
            entry_rationale=pos.rationale,
            exit_rationale=exit_rationale,
            contributing_models=resolved_models or {}
        )

        # Feed into Adaptive Learner for feedback loop!
        mistake = self.learner.evaluate_closed_trade(trade_record)
        if mistake:
            trade_record.mistake_analysis = mistake.primary_failure_cause

        self.trade_ledger.insert(0, trade_record)
        if len(self.trade_ledger) > 100:
            self.trade_ledger.pop()

        self.save_state()
        return trade_record

    def save_state(self):
        """Persists portfolio ledger and learned weights to disk."""
        if not self.db_path:
            return
        try:
            state = {
                "initial_capital": self.initial_capital,
                "cash": self.cash,
                "peak_equity": self.peak_equity,
                "positions": {k: v.model_dump() for k, v in self.positions.items()},
                "trade_ledger": [t.model_dump() for t in self.trade_ledger],
                "learner_weights": self.learner.weights,
                "mistake_history": [m.model_dump() for m in self.learner.mistake_history],
                "total_trades_evaluated": self.learner.total_trades_evaluated,
                "winning_trades_count": self.learner.winning_trades_count,
                "losing_trades_count": self.learner.losing_trades_count,
                "total_win_usd": self.learner.total_win_usd,
                "total_loss_usd": self.learner.total_loss_usd
            }
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def load_state(self):
        """Loads persistent portfolio ledger and learner parameters."""
        if not self.db_path or not os.path.exists(self.db_path):
            return
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.initial_capital = state.get("initial_capital", 10000.0)
            self.cash = state.get("cash", 10000.0)
            self.peak_equity = state.get("peak_equity", self.cash)
            
            raw_pos = state.get("positions", {})
            self.positions = {k: Position(**v) for k, v in raw_pos.items()}
            
            raw_trades = state.get("trade_ledger", [])
            self.trade_ledger = [TradeRecord(**t) for t in raw_trades]

            if "learner_weights" in state:
                self.learner.weights = state["learner_weights"]
            if "total_trades_evaluated" in state:
                self.learner.total_trades_evaluated = state.get("total_trades_evaluated", 0)
                self.learner.winning_trades_count = state.get("winning_trades_count", 0)
                self.learner.losing_trades_count = state.get("losing_trades_count", 0)
                self.learner.total_win_usd = state.get("total_win_usd", 0.0)
                self.learner.total_loss_usd = state.get("total_loss_usd", 0.0)
        except Exception:
            pass

    def get_per_stock_summary(self, trades_list: Optional[List[TradeRecord]] = None) -> List[StockPerformanceSummary]:
        """
        Groups trades by individual stock symbol and calculates:
        - Amount traded ($ volume)
        - Total number of trades
        - Hits (winning trades)
        - Misses (losing trades)
        - Hit Rate (%)
        - Total P&L in dollars up/down ($)
        - Total Return (%)
        """
        trades = trades_list if trades_list is not None else self.trade_ledger
        by_symbol: Dict[str, List[TradeRecord]] = {}
        for t in trades:
            sym = t.symbol.upper()
            if sym not in by_symbol:
                by_symbol[sym] = []
            by_symbol[sym].append(t)

        summaries: List[StockPerformanceSummary] = []
        for sym, s_trades in by_symbol.items():
            amt_traded = sum(t.cost_basis_usd for t in s_trades)
            total_tr = len(s_trades)
            hits = sum(1 for t in s_trades if t.win)
            misses = sum(1 for t in s_trades if not t.win)
            hit_rate = (hits / total_tr * 100.0) if total_tr > 0 else 0.0
            net_pnl = sum(t.realized_pnl_usd for t in s_trades)
            net_pnl_pct = (net_pnl / amt_traded * 100.0) if amt_traded > 0 else 0.0
            avg_pnl = net_pnl / total_tr if total_tr > 0 else 0.0

            summaries.append(StockPerformanceSummary(
                symbol=sym,
                amount_traded_usd=round(amt_traded, 2),
                total_trades=total_tr,
                hits=hits,
                misses=misses,
                hit_rate_pct=round(hit_rate, 1),
                net_pnl_usd=round(net_pnl, 2),
                net_pnl_pct=round(net_pnl_pct, 2),
                average_trade_pnl_usd=round(avg_pnl, 2)
            ))

        # Sort by net P&L descending (top performers first)
        summaries.sort(key=lambda s: s.net_pnl_usd, reverse=True)
        return summaries

    def get_multi_day_report(self, days: int = 5) -> MultiDayPerformanceReport:
        """
        Aggregates performance over the last N working days per stock and in grand total.
        """
        now_utc = datetime.now(timezone.utc)
        stock_summaries = self.get_per_stock_summary(self.trade_ledger)

        # Calculate portfolio grand totals
        total_vol = sum(s.amount_traded_usd for s in stock_summaries)
        total_tr = sum(s.total_trades for s in stock_summaries)
        total_hits = sum(s.hits for s in stock_summaries)
        total_misses = sum(s.misses for s in stock_summaries)
        overall_hit_rate = (total_hits / total_tr * 100.0) if total_tr > 0 else 0.0
        total_net_pnl = sum(s.net_pnl_usd for s in stock_summaries)
        total_net_pct = (total_net_pnl / total_vol * 100.0) if total_vol > 0 else 0.0

        return MultiDayPerformanceReport(
            period_title=f"Last {days} Working Days Cumulative Performance",
            total_amount_traded_usd=round(total_vol, 2),
            total_trades=total_tr,
            total_hits=total_hits,
            total_misses=total_misses,
            overall_hit_rate_pct=round(overall_hit_rate, 1),
            total_net_pnl_usd=round(total_net_pnl, 2),
            total_net_pnl_pct=round(total_net_pct, 2),
            stock_summaries=stock_summaries,
            generated_at_uk=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        )

