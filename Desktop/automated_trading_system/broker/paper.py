"""
Paper broker — simulates order execution with virtual money.

Default broker for the system. No real money involved.
Supports the same interface as live brokers for seamless switching.
"""

from datetime import datetime
from typing import Dict, List, Optional
import uuid

import config
from .base import BrokerBase, OrderResult, Position, AccountInfo


class PaperBroker(BrokerBase):
    """Simulated broker for paper trading."""

    def __init__(self, initial_capital: float = None, commission_rate: float = None,
                 slippage_rate: float = None):
        self.initial_capital = initial_capital or config.INITIAL_CAPITAL
        self.cash = self.initial_capital
        self.commission_rate = commission_rate or config.COMMISSION_RATE
        self.slippage_rate = slippage_rate or config.SLIPPAGE_RATE
        self._connected = False
        self._positions: Dict[str, dict] = {}  # {symbol: {quantity, avg_cost}}
        self._orders: Dict[str, OrderResult] = {}
        self._daily_pnl = 0.0

    @property
    def name(self) -> str:
        return "Paper Trading"

    @property
    def is_live(self) -> bool:
        return False

    def connect(self, **credentials) -> bool:
        """Paper broker always connects successfully."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> AccountInfo:
        positions_value = sum(
            p["quantity"] * p["avg_cost"] for p in self._positions.values()
        )
        return AccountInfo(
            broker_name=self.name,
            is_connected=self._connected,
            available_cash=round(self.cash, 2),
            total_value=round(self.cash + positions_value, 2),
            used_margin=round(positions_value, 2),
            positions_count=len(self._positions),
        )

    def place_order(self, symbol: str, side: str, quantity: int,
                    order_type: str = "MARKET", price: float = 0.0,
                    trigger_price: float = 0.0) -> OrderResult:
        """Simulate order execution."""
        order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now()

        # For paper trading, use provided price as execution price
        exec_price = price if price > 0 else 0

        if exec_price <= 0:
            return OrderResult(
                success=False, order_id=order_id, symbol=symbol, side=side,
                quantity=quantity, message="Price must be > 0 for paper trades",
                timestamp=now,
            )

        if side == "BUY":
            commission = exec_price * quantity * self.commission_rate
            slippage = exec_price * quantity * self.slippage_rate
            total_cost = exec_price * quantity + commission + slippage

            if total_cost > self.cash:
                # Buy what we can afford
                quantity = int(self.cash / (exec_price * (1 + self.commission_rate + self.slippage_rate)))
                if quantity <= 0:
                    return OrderResult(
                        success=False, order_id=order_id, symbol=symbol, side=side,
                        quantity=0, message="Insufficient funds", timestamp=now,
                    )
                commission = exec_price * quantity * self.commission_rate
                slippage = exec_price * quantity * self.slippage_rate
                total_cost = exec_price * quantity + commission + slippage

            self.cash -= total_cost

            if symbol in self._positions:
                pos = self._positions[symbol]
                total_qty = pos["quantity"] + quantity
                pos["avg_cost"] = (pos["avg_cost"] * pos["quantity"] + exec_price * quantity) / total_qty
                pos["quantity"] = total_qty
            else:
                self._positions[symbol] = {"quantity": quantity, "avg_cost": exec_price}

            result = OrderResult(
                success=True, order_id=order_id, symbol=symbol, side="BUY",
                quantity=quantity, price=exec_price, order_type=order_type,
                status="COMPLETE", message="Paper BUY executed",
                timestamp=now, commission=round(commission, 2),
            )

        elif side == "SELL":
            if symbol not in self._positions or self._positions[symbol]["quantity"] <= 0:
                return OrderResult(
                    success=False, order_id=order_id, symbol=symbol, side=side,
                    quantity=0, message=f"No position in {symbol}", timestamp=now,
                )

            pos = self._positions[symbol]
            quantity = min(quantity, pos["quantity"])
            commission = exec_price * quantity * self.commission_rate
            slippage = exec_price * quantity * self.slippage_rate
            proceeds = exec_price * quantity - commission - slippage
            pnl = proceeds - (pos["avg_cost"] * quantity)

            self.cash += proceeds
            self._daily_pnl += pnl
            pos["quantity"] -= quantity

            if pos["quantity"] <= 0:
                del self._positions[symbol]

            result = OrderResult(
                success=True, order_id=order_id, symbol=symbol, side="SELL",
                quantity=quantity, price=exec_price, order_type=order_type,
                status="COMPLETE", message="Paper SELL executed",
                timestamp=now, commission=round(commission, 2), pnl=round(pnl, 2),
            )
        else:
            return OrderResult(
                success=False, order_id=order_id, symbol=symbol, side=side,
                message=f"Unknown side: {side}", timestamp=now,
            )

        self._orders[order_id] = result
        return result

    def get_positions(self) -> List[Position]:
        """Get all paper positions."""
        positions = []
        for symbol, data in self._positions.items():
            if data["quantity"] > 0:
                positions.append(Position(
                    symbol=symbol,
                    quantity=data["quantity"],
                    avg_cost=round(data["avg_cost"], 2),
                    current_price=round(data["avg_cost"], 2),  # Paper uses avg_cost
                ))
        return positions

    def get_live_price(self, symbol: str) -> float:
        """Paper broker returns 0 — use yfinance for actual prices."""
        return 0.0

    def cancel_order(self, order_id: str) -> bool:
        """Paper orders execute instantly, nothing to cancel."""
        return False

    def get_daily_pnl(self) -> float:
        """Get daily realized P&L."""
        return round(self._daily_pnl, 2)

    def reset_daily_pnl(self) -> None:
        """Reset daily P&L counter (call at start of each day)."""
        self._daily_pnl = 0.0
