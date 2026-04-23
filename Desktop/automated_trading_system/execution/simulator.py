"""
Paper trading simulator — simulates live order execution without real money.

Tracks portfolio state, logs all trades to the database, and applies
realistic commission and slippage costs.
"""

from datetime import datetime
from typing import Dict, Optional

import config
from database.db_manager import DatabaseManager


def _safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


class PaperTrader:
    """
    Simulates order execution for paper trading.

    Maintains an in-memory portfolio and logs all trades to the database.
    """

    def __init__(
        self,
        strategy_name: str,
        initial_capital: float = None,
        commission_rate: float = None,
        slippage_rate: float = None,
        db_manager: DatabaseManager = None,
    ):
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital or config.INITIAL_CAPITAL
        self.cash = self.initial_capital
        self.commission_rate = commission_rate or config.COMMISSION_RATE
        self.slippage_rate = slippage_rate or config.SLIPPAGE_RATE
        self.db = db_manager or DatabaseManager()

        # In-memory portfolio: {symbol: {"quantity": float, "avg_cost": float}}
        self.positions: Dict[str, Dict[str, float]] = {}

    @property
    def portfolio_value(self) -> float:
        """Current total portfolio value (cash + positions at avg cost)."""
        positions_value = sum(
            pos["quantity"] * pos["avg_cost"] for pos in self.positions.values()
        )
        return self.cash + positions_value

    def execute_buy(self, symbol: str, quantity: int, price: float,
                    timestamp: datetime = None) -> Optional[Dict]:
        """
        Execute a simulated BUY order.

        Args:
            symbol: Ticker symbol
            quantity: Number of shares to buy
            price: Execution price per share
            timestamp: Trade timestamp

        Returns:
            Trade details dict or None if insufficient funds
        """
        commission = price * quantity * self.commission_rate
        slippage = price * quantity * self.slippage_rate
        total_cost = price * quantity + commission + slippage

        # Check funds
        if total_cost > self.cash:
            # Buy what we can afford
            quantity = int(self.cash / (price * (1 + self.commission_rate + self.slippage_rate)))
            if quantity <= 0:
                _safe_print(f"   [WARN] Insufficient funds to buy {symbol}.")
                return None
            commission = price * quantity * self.commission_rate
            slippage = price * quantity * self.slippage_rate
            total_cost = price * quantity + commission + slippage

        # Deduct cash
        self.cash -= total_cost

        # Update position
        if symbol in self.positions:
            existing = self.positions[symbol]
            total_qty = existing["quantity"] + quantity
            existing["avg_cost"] = (
                (existing["avg_cost"] * existing["quantity"] + price * quantity) / total_qty
            )
            existing["quantity"] = total_qty
        else:
            self.positions[symbol] = {
                "quantity": quantity,
                "avg_cost": price,
            }

        # Save to DB
        self.db.save_trade(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=price,
            commission=commission,
            slippage=slippage,
            total_cost=total_cost,
            strategy_name=self.strategy_name,
            timestamp=timestamp,
        )

        # Update portfolio in DB
        pos = self.positions[symbol]
        self.db.update_portfolio(symbol, pos["quantity"], pos["avg_cost"], price)

        trade_detail = {
            "side": "BUY",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "commission": round(commission, 2),
            "slippage": round(slippage, 2),
            "total_cost": round(total_cost, 2),
            "cash_remaining": round(self.cash, 2),
        }

        cs = config.CURRENCY_SYMBOL
        _safe_print(f"   [BUY] BUY  {quantity} {symbol} @ {cs}{price:.2f}  "
                    f"(cost: {cs}{total_cost:.2f}, cash: {cs}{self.cash:,.2f})")

        return trade_detail

    def execute_sell(self, symbol: str, quantity: int, price: float,
                     timestamp: datetime = None) -> Optional[Dict]:
        """
        Execute a simulated SELL order.

        Args:
            symbol: Ticker symbol
            quantity: Number of shares to sell
            price: Execution price per share
            timestamp: Trade timestamp

        Returns:
            Trade details dict or None if no position
        """
        if symbol not in self.positions or self.positions[symbol]["quantity"] <= 0:
            _safe_print(f"   [WARN] No position in {symbol} to sell.")
            return None

        position = self.positions[symbol]
        quantity = min(quantity, int(position["quantity"]))

        commission = price * quantity * self.commission_rate
        slippage = price * quantity * self.slippage_rate
        proceeds = price * quantity - commission - slippage

        # Compute P&L
        cost_basis = position["avg_cost"] * quantity
        pnl = proceeds - cost_basis

        # Add proceeds to cash
        self.cash += proceeds

        # Update position
        position["quantity"] -= quantity
        if position["quantity"] <= 0:
            del self.positions[symbol]

        # Save to DB
        self.db.save_trade(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            price=price,
            commission=commission,
            slippage=slippage,
            total_cost=proceeds,
            pnl=pnl,
            strategy_name=self.strategy_name,
            timestamp=timestamp,
        )

        # Update portfolio in DB
        if symbol in self.positions:
            pos = self.positions[symbol]
            self.db.update_portfolio(symbol, pos["quantity"], pos["avg_cost"], price)

        trade_detail = {
            "side": "SELL",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "commission": round(commission, 2),
            "slippage": round(slippage, 2),
            "proceeds": round(proceeds, 2),
            "pnl": round(pnl, 2),
            "cash_remaining": round(self.cash, 2),
        }

        cs = config.CURRENCY_SYMBOL
        tag = "[PROFIT]" if pnl >= 0 else "[LOSS]"
        _safe_print(f"   {tag} SELL {quantity} {symbol} @ {cs}{price:.2f}  "
                    f"(P&L: {cs}{pnl:,.2f}, cash: {cs}{self.cash:,.2f})")

        return trade_detail

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for a symbol."""
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Dict]:
        """Get all current positions."""
        return self.positions.copy()

    def get_status(self) -> Dict:
        """Get overall paper trading status."""
        total_invested = sum(
            pos["quantity"] * pos["avg_cost"] for pos in self.positions.values()
        )
        return {
            "cash": round(self.cash, 2),
            "positions_value": round(total_invested, 2),
            "total_value": round(self.cash + total_invested, 2),
            "return_pct": round(
                ((self.cash + total_invested - self.initial_capital) / self.initial_capital) * 100, 2
            ),
            "num_positions": len(self.positions),
            "positions": {
                sym: {
                    "quantity": pos["quantity"],
                    "avg_cost": round(pos["avg_cost"], 2),
                    "value": round(pos["quantity"] * pos["avg_cost"], 2),
                }
                for sym, pos in self.positions.items()
            },
        }
