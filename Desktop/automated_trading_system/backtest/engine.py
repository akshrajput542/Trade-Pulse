"""
Backtesting engine — simulates strategy performance against historical data.

Features:
    - Simulates long-only trades with configurable commission & slippage
    - Tracks full equity curve, drawdowns, and trade log
    - Computes: total return, Sharpe ratio, max drawdown, win rate, and more
"""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd

import config
from strategy.base import Strategy
from data.fetcher import DataFetcher
from database.db_manager import DatabaseManager


def _safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


@dataclass
class TradeRecord:
    """A single trade in the backtest."""
    date: Any
    side: str          # BUY or SELL
    price: float
    quantity: float
    commission: float
    slippage: float
    total_cost: float
    portfolio_value: float
    pnl: float = 0.0


@dataclass
class BacktestResult:
    """Container for backtest results."""
    strategy_name: str
    symbol: str
    start_date: date
    end_date: date
    initial_capital: float
    final_value: float
    total_return_pct: float
    sharpe_ratio: Optional[float]
    max_drawdown_pct: Optional[float]
    win_rate: Optional[float]
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_pnl: Optional[float]
    equity_curve: List[float]
    trade_log: List[TradeRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "final_value": round(self.final_value, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4) if self.sharpe_ratio else None,
            "max_drawdown_pct": round(self.max_drawdown_pct, 2) if self.max_drawdown_pct else None,
            "win_rate": round(self.win_rate, 2) if self.win_rate else None,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_pnl": round(self.avg_trade_pnl, 2) if self.avg_trade_pnl else None,
            "equity_curve": [round(v, 2) for v in self.equity_curve],
        }

    def summary(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"  Backtest Results: {self.strategy_name}\n"
            f"  Symbol: {self.symbol}  |  {self.start_date} -> {self.end_date}\n"
            f"{'='*60}\n"
            f"  Initial Capital:  ${self.initial_capital:>12,.2f}\n"
            f"  Final Value:      ${self.final_value:>12,.2f}\n"
            f"  Total Return:     {self.total_return_pct:>11.2f}%\n"
            f"  Sharpe Ratio:     {self.sharpe_ratio or 0:>11.4f}\n"
            f"  Max Drawdown:     {self.max_drawdown_pct or 0:>11.2f}%\n"
            f"{'-'*60}\n"
            f"  Total Trades:     {self.total_trades:>11}\n"
            f"  Winning Trades:   {self.winning_trades:>11}\n"
            f"  Losing Trades:    {self.losing_trades:>11}\n"
            f"  Win Rate:         {self.win_rate or 0:>11.2f}%\n"
            f"  Avg Trade P&L:    ${self.avg_trade_pnl or 0:>11.2f}\n"
            f"{'='*60}\n"
        )


class BacktestEngine:
    """
    Backtesting engine that simulates a strategy on historical data.

    Supports:
        - Long-only trading
        - Commission & slippage costs
        - Full equity curve tracking
        - Performance metrics computation
    """

    def __init__(
        self,
        strategy: Strategy,
        initial_capital: float = None,
        commission_rate: float = None,
        slippage_rate: float = None,
        db_manager: DatabaseManager = None,
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital or config.INITIAL_CAPITAL
        self.commission_rate = commission_rate or config.COMMISSION_RATE
        self.slippage_rate = slippage_rate or config.SLIPPAGE_RATE
        self.db = db_manager or DatabaseManager()
        self.fetcher = DataFetcher(db_manager=self.db)

    def run(
        self,
        symbol: str,
        start: str = None,
        end: str = None,
        data: pd.DataFrame = None,
        save_to_db: bool = True,
    ) -> BacktestResult:
        """
        Run a backtest for a given symbol and date range.

        Args:
            symbol: Ticker symbol
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            data: Optional pre-fetched DataFrame (skips fetch)
            save_to_db: Whether to save results to database

        Returns:
            BacktestResult with all metrics and equity curve
        """
        start = start or config.DEFAULT_START_DATE
        end = end or config.DEFAULT_END_DATE

        _safe_print(f"\n[BACKTEST] Running backtest: {self.strategy.name} on {symbol} ({start} -> {end})")

        # ── Get data ──
        if data is None:
            data = self.fetcher.fetch_historical_data(symbol, start=start, end=end, save_to_db=True)

        if data.empty:
            _safe_print("   [ERROR] No data available for backtest.")
            return self._empty_result(symbol, start, end)

        # ── Generate signals ──
        signals_df = self.strategy.generate_signals(data)

        # ── Simulate trades ──
        result = self._simulate(signals_df, symbol, start, end)

        # ── Save to DB ──
        if save_to_db:
            self.db.save_backtest_result(result.to_dict())

        _safe_print(result.summary())
        return result

    def _simulate(self, df: pd.DataFrame, symbol: str, start: str, end: str) -> BacktestResult:
        """Core simulation loop."""
        cash = self.initial_capital
        shares = 0
        equity_curve = []
        trade_log = []
        buy_price = 0.0

        for i in range(len(df)):
            row = df.iloc[i]
            price = row["Close"]
            signal = row.get("Signal", 0)

            # ── Execute BUY ──
            if signal == 1 and shares == 0:
                # Buy as many shares as we can afford
                max_shares = int(cash / (price * (1 + self.commission_rate + self.slippage_rate)))
                if max_shares > 0:
                    commission = price * max_shares * self.commission_rate
                    slippage = price * max_shares * self.slippage_rate
                    total_cost = price * max_shares + commission + slippage

                    shares = max_shares
                    cash -= total_cost
                    buy_price = price

                    trade_log.append(TradeRecord(
                        date=df.index[i],
                        side="BUY",
                        price=price,
                        quantity=max_shares,
                        commission=commission,
                        slippage=slippage,
                        total_cost=total_cost,
                        portfolio_value=cash + shares * price,
                    ))

            # ── Execute SELL ──
            elif signal == -1 and shares > 0:
                commission = price * shares * self.commission_rate
                slippage = price * shares * self.slippage_rate
                proceeds = price * shares - commission - slippage
                pnl = proceeds - (buy_price * shares)

                cash += proceeds

                trade_log.append(TradeRecord(
                    date=df.index[i],
                    side="SELL",
                    price=price,
                    quantity=shares,
                    commission=commission,
                    slippage=slippage,
                    total_cost=proceeds,
                    portfolio_value=cash,
                    pnl=pnl,
                ))

                shares = 0

            # Track equity
            portfolio_value = cash + shares * price
            equity_curve.append(portfolio_value)

        # ── Close open position at the end ──
        if shares > 0:
            final_price = df.iloc[-1]["Close"]
            cash += shares * final_price * (1 - self.commission_rate - self.slippage_rate)
            shares = 0

        final_value = cash
        total_return = ((final_value - self.initial_capital) / self.initial_capital) * 100

        # ── Compute metrics ──
        sell_trades = [t for t in trade_log if t.side == "SELL"]
        winning = [t for t in sell_trades if t.pnl > 0]
        losing = [t for t in sell_trades if t.pnl <= 0]
        pnls = [t.pnl for t in sell_trades]

        sharpe = self._compute_sharpe(equity_curve)
        max_dd = self._compute_max_drawdown(equity_curve)

        return BacktestResult(
            strategy_name=self.strategy.name,
            symbol=symbol,
            start_date=pd.to_datetime(start).date(),
            end_date=pd.to_datetime(end).date(),
            initial_capital=self.initial_capital,
            final_value=final_value,
            total_return_pct=total_return,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            win_rate=(len(winning) / len(sell_trades) * 100) if sell_trades else 0,
            total_trades=len(trade_log),
            winning_trades=len(winning),
            losing_trades=len(losing),
            avg_trade_pnl=(sum(pnls) / len(pnls)) if pnls else 0,
            equity_curve=equity_curve,
            trade_log=trade_log,
        )

    def _compute_sharpe(self, equity_curve: List[float]) -> Optional[float]:
        """Compute annualized Sharpe Ratio from equity curve."""
        if len(equity_curve) < 2:
            return None
        returns = pd.Series(equity_curve).pct_change().dropna()
        if returns.std() == 0:
            return 0.0
        excess_return = returns.mean() - (config.RISK_FREE_RATE / config.TRADING_DAYS_PER_YEAR)
        return float(excess_return / returns.std() * np.sqrt(config.TRADING_DAYS_PER_YEAR))

    def _compute_max_drawdown(self, equity_curve: List[float]) -> Optional[float]:
        """Compute maximum drawdown percentage from equity curve."""
        if len(equity_curve) < 2:
            return None
        curve = pd.Series(equity_curve)
        peak = curve.cummax()
        drawdown = (curve - peak) / peak * 100
        return float(drawdown.min())

    def _empty_result(self, symbol: str, start: str, end: str) -> BacktestResult:
        """Return an empty result when no data is available."""
        return BacktestResult(
            strategy_name=self.strategy.name,
            symbol=symbol,
            start_date=pd.to_datetime(start).date(),
            end_date=pd.to_datetime(end).date(),
            initial_capital=self.initial_capital,
            final_value=self.initial_capital,
            total_return_pct=0.0,
            sharpe_ratio=None,
            max_drawdown_pct=None,
            win_rate=None,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_trade_pnl=None,
            equity_curve=[],
        )
