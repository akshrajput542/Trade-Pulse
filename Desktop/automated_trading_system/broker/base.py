"""
Abstract broker interface.

All broker implementations (paper, Zerodha, Angel) must implement this interface
so the rest of the system can swap brokers transparently.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class OrderResult:
    """Standardized order result across all brokers."""
    success: bool
    order_id: str = ""
    symbol: str = ""
    side: str = ""             # BUY or SELL
    quantity: int = 0
    price: float = 0.0
    order_type: str = "MARKET" # MARKET, LIMIT, SL, SL-M
    status: str = ""           # COMPLETE, PENDING, REJECTED
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    commission: float = 0.0
    pnl: float = 0.0


@dataclass
class Position:
    """Standardized position across all brokers."""
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class AccountInfo:
    """Standardized account info across all brokers."""
    broker_name: str
    is_connected: bool = False
    available_cash: float = 0.0
    total_value: float = 0.0
    used_margin: float = 0.0
    positions_count: int = 0


class BrokerBase(ABC):
    """Abstract base class for all broker implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Broker display name."""
        pass

    @property
    @abstractmethod
    def is_live(self) -> bool:
        """True if real money broker, False for paper."""
        pass

    @abstractmethod
    def connect(self, **credentials) -> bool:
        """
        Authenticate and establish connection with broker.

        Args:
            **credentials: Broker-specific auth params (api_key, password, etc.)

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close broker connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if broker connection is active."""
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Get account balance and summary."""
        pass

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = 0.0,
        trigger_price: float = 0.0,
    ) -> OrderResult:
        """
        Place a buy or sell order.

        Args:
            symbol: Ticker symbol
            side: "BUY" or "SELL"
            quantity: Number of shares
            order_type: MARKET, LIMIT, SL, SL-M
            price: Limit price (for LIMIT orders)
            trigger_price: Stop loss trigger (for SL orders)

        Returns:
            OrderResult with execution details
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all current open positions."""
        pass

    @abstractmethod
    def get_live_price(self, symbol: str) -> float:
        """Get real-time last traded price for a symbol."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if successful."""
        pass

    def close_all_positions(self) -> List[OrderResult]:
        """Emergency: close all open positions at market price."""
        results = []
        for pos in self.get_positions():
            if pos.quantity > 0:
                result = self.place_order(
                    symbol=pos.symbol,
                    side="SELL",
                    quantity=pos.quantity,
                    order_type="MARKET",
                )
                results.append(result)
        return results
