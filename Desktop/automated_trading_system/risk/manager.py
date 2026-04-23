"""
Risk Manager — core risk management engine.

Protects beginners by enforcing:
    - Stop loss per position
    - Trailing stop to lock in profits
    - Take profit auto-exit
    - Max daily loss halt
    - Position size limits
    - Max concurrent positions
    - Cooldown period after exits
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import config


@dataclass
class PositionRisk:
    """Risk state for a single position."""
    symbol: str
    entry_price: float
    current_price: float = 0.0
    quantity: int = 0
    highest_price: float = 0.0     # For trailing stop
    stop_loss_price: float = 0.0
    trailing_stop_price: float = 0.0
    take_profit_price: float = 0.0
    entry_time: datetime = field(default_factory=datetime.now)

    @property
    def pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    @property
    def risk_level(self) -> str:
        """Green/Yellow/Red risk indicator."""
        pct = self.pnl_pct
        if pct >= 5:
            return "green"
        elif pct >= -2:
            return "yellow"
        else:
            return "red"


class RiskManager:
    """Central risk management engine."""

    def __init__(
        self,
        stop_loss_pct: float = None,
        trailing_stop_pct: float = None,
        take_profit_pct: float = None,
        max_daily_loss_pct: float = None,
        max_position_pct: float = None,
        max_open_positions: int = None,
        cooldown_hours: int = None,
        initial_capital: float = None,
    ):
        self.stop_loss_pct = stop_loss_pct or config.RISK_STOP_LOSS_PCT
        self.trailing_stop_pct = trailing_stop_pct or config.RISK_TRAILING_STOP_PCT
        self.take_profit_pct = take_profit_pct or config.RISK_TAKE_PROFIT_PCT
        self.max_daily_loss_pct = max_daily_loss_pct or config.RISK_MAX_DAILY_LOSS_PCT
        self.max_position_pct = max_position_pct or config.RISK_MAX_POSITION_PCT
        self.max_open_positions = max_open_positions or config.RISK_MAX_OPEN_POSITIONS
        self.cooldown_hours = cooldown_hours or config.RISK_COOLDOWN_HOURS
        self.initial_capital = initial_capital or config.INITIAL_CAPITAL

        self._positions: Dict[str, PositionRisk] = {}
        self._daily_pnl: float = 0.0
        self._daily_reset_date: datetime = datetime.now().date()
        self._exit_times: Dict[str, datetime] = {}  # symbol -> last exit time
        self._trading_halted: bool = False

    def register_position(self, symbol: str, entry_price: float, quantity: int):
        """Register new position for risk tracking."""
        sl_price = entry_price * (1 - self.stop_loss_pct / 100)
        tp_price = entry_price * (1 + self.take_profit_pct / 100)

        self._positions[symbol] = PositionRisk(
            symbol=symbol,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            highest_price=entry_price,
            stop_loss_price=round(sl_price, 2),
            trailing_stop_price=round(sl_price, 2),
            take_profit_price=round(tp_price, 2),
        )

    def update_price(self, symbol: str, current_price: float) -> List[str]:
        """
        Update price and check risk triggers.

        Returns list of triggered actions: ["STOP_LOSS", "TRAILING_STOP", "TAKE_PROFIT"]
        """
        if symbol not in self._positions:
            return []

        pos = self._positions[symbol]
        pos.current_price = current_price
        triggers = []

        # Update highest price (for trailing stop)
        if current_price > pos.highest_price:
            pos.highest_price = current_price
            # Move trailing stop up
            new_trail = current_price * (1 - self.trailing_stop_pct / 100)
            if new_trail > pos.trailing_stop_price:
                pos.trailing_stop_price = round(new_trail, 2)

        # Check stop loss
        if current_price <= pos.stop_loss_price:
            triggers.append("STOP_LOSS")

        # Check trailing stop
        if current_price <= pos.trailing_stop_price and pos.pnl_pct > 0:
            triggers.append("TRAILING_STOP")

        # Check take profit
        if current_price >= pos.take_profit_price:
            triggers.append("TAKE_PROFIT")

        return triggers

    def can_open_position(self, symbol: str, cost: float, portfolio_value: float) -> Tuple[bool, str]:
        """
        Check if a new position can be opened.

        Returns (allowed, reason).
        """
        # Check trading halt
        self._check_daily_reset()
        if self._trading_halted:
            return False, f"Trading halted: daily loss exceeds {self.max_daily_loss_pct}%"

        # Check max positions
        if len(self._positions) >= self.max_open_positions:
            return False, f"Max {self.max_open_positions} positions reached"

        # Check position size limit
        max_cost = portfolio_value * (self.max_position_pct / 100)
        if cost > max_cost:
            return False, f"Position too large: {config.CURRENCY_SYMBOL}{cost:,.0f} > {self.max_position_pct}% limit"

        # Check cooldown
        if symbol in self._exit_times:
            elapsed = datetime.now() - self._exit_times[symbol]
            if elapsed < timedelta(hours=self.cooldown_hours):
                remaining = timedelta(hours=self.cooldown_hours) - elapsed
                return False, f"Cooldown: {remaining.seconds // 60} min remaining for {symbol}"

        # Check duplicate
        if symbol in self._positions:
            return False, f"Already holding {symbol}"

        return True, "OK"

    def record_exit(self, symbol: str, pnl: float):
        """Record position exit for cooldown and daily P&L tracking."""
        self._daily_pnl += pnl
        self._exit_times[symbol] = datetime.now()

        if symbol in self._positions:
            del self._positions[symbol]

        # Check daily loss limit
        max_loss = self.initial_capital * (self.max_daily_loss_pct / 100)
        if self._daily_pnl < -max_loss:
            self._trading_halted = True

    def _check_daily_reset(self):
        """Reset daily counters at start of new day."""
        today = datetime.now().date()
        if today > self._daily_reset_date:
            self._daily_pnl = 0.0
            self._trading_halted = False
            self._daily_reset_date = today

    def get_position_risk(self, symbol: str) -> Optional[PositionRisk]:
        return self._positions.get(symbol)

    def get_all_risks(self) -> Dict[str, PositionRisk]:
        return self._positions.copy()

    def get_portfolio_risk_score(self) -> int:
        """Overall portfolio risk score 0-100 (100 = safest)."""
        if not self._positions:
            return 100

        scores = []
        for pos in self._positions.values():
            if pos.pnl_pct >= 5:
                scores.append(90)
            elif pos.pnl_pct >= 0:
                scores.append(70)
            elif pos.pnl_pct >= -2:
                scores.append(50)
            elif pos.pnl_pct >= -5:
                scores.append(25)
            else:
                scores.append(10)

        avg = sum(scores) / len(scores)

        # Penalize for concentration
        if len(self._positions) >= self.max_open_positions:
            avg *= 0.9

        # Penalize for daily loss
        if self._daily_pnl < 0:
            loss_ratio = abs(self._daily_pnl) / (self.initial_capital * self.max_daily_loss_pct / 100)
            avg *= max(0.5, 1 - loss_ratio * 0.3)

        return max(0, min(100, int(avg)))

    @property
    def is_trading_halted(self) -> bool:
        self._check_daily_reset()
        return self._trading_halted

    @property
    def daily_pnl(self) -> float:
        return round(self._daily_pnl, 2)

    def get_status(self) -> dict:
        """Get risk management status summary."""
        return {
            "positions_tracked": len(self._positions),
            "daily_pnl": self.daily_pnl,
            "trading_halted": self.is_trading_halted,
            "portfolio_risk_score": self.get_portfolio_risk_score(),
            "max_daily_loss": round(self.initial_capital * self.max_daily_loss_pct / 100, 2),
            "positions": {
                sym: {
                    "pnl": round(p.pnl, 2),
                    "pnl_pct": round(p.pnl_pct, 2),
                    "risk_level": p.risk_level,
                    "stop_loss": p.stop_loss_price,
                    "trailing_stop": p.trailing_stop_price,
                    "take_profit": p.take_profit_price,
                }
                for sym, p in self._positions.items()
            },
        }
