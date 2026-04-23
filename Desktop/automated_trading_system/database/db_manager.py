"""
Database manager — handles session lifecycle and all CRUD operations.
"""

import json
import sys
from datetime import datetime, date
from typing import List, Optional, Dict, Any

import pandas as pd
from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker, Session

from .models import (
    Base, MarketData, Signal, Trade, Portfolio, BacktestResult,
    User, AutoTradeConfig, RiskEvent, Watchlist, Recommendation, BrokerState,
)
import config


def _safe_print(msg: str):
    """Print with fallback for Windows consoles that can't handle Unicode."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


class DatabaseManager:
    """Manages database connections and provides CRUD helpers."""

    def __init__(self, db_url: str = None):
        self.db_url = db_url or config.DATABASE_URL
        self.engine = create_engine(self.db_url, echo=False)
        self._SessionFactory = sessionmaker(bind=self.engine)

    # ── Lifecycle ──────────────────────────────────
    def init_db(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)
        _safe_print("[OK] Database initialized.")

    def get_session(self) -> Session:
        """Return a new SQLAlchemy session for direct use."""
        return self._SessionFactory()

    # ── Market Data ────────────────────────────────
    def save_market_data(self, df: pd.DataFrame, symbol: str):
        """Upsert OHLCV DataFrame into market_data table."""
        session = self.get_session()
        try:
            records_saved = 0
            for _, row in df.iterrows():
                row_date = row.name if isinstance(row.name, (datetime, date)) else row.get("Date")
                if isinstance(row_date, datetime):
                    row_date = row_date.date()

                existing = (
                    session.query(MarketData)
                    .filter_by(symbol=symbol, date=row_date)
                    .first()
                )
                if existing:
                    existing.open = float(row["Open"])
                    existing.high = float(row["High"])
                    existing.low = float(row["Low"])
                    existing.close = float(row["Close"])
                    existing.volume = float(row.get("Volume", 0))
                else:
                    session.add(MarketData(
                        symbol=symbol, date=row_date,
                        open=float(row["Open"]), high=float(row["High"]),
                        low=float(row["Low"]), close=float(row["Close"]),
                        volume=float(row.get("Volume", 0)),
                    ))
                    records_saved += 1
            session.commit()
            _safe_print(f"   [SAVED] {symbol}: {records_saved} new records saved, {len(df) - records_saved} updated.")
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving market data for {symbol}: {e}")
        finally:
            session.close()

    def get_market_data(self, symbol: str, start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """Retrieve market data as a DataFrame."""
        session = self.get_session()
        try:
            query = session.query(MarketData).filter(MarketData.symbol == symbol)
            if start_date:
                query = query.filter(MarketData.date >= start_date)
            if end_date:
                query = query.filter(MarketData.date <= end_date)
            query = query.order_by(MarketData.date)

            records = query.all()
            if not records:
                return pd.DataFrame()

            data = [{
                "Date": r.date, "Open": r.open, "High": r.high,
                "Low": r.low, "Close": r.close, "Volume": r.volume,
            } for r in records]

            df = pd.DataFrame(data)
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
            return df
        finally:
            session.close()

    # ── Signals ────────────────────────────────────
    def save_signal(self, symbol: str, strategy_name: str, signal_type: str,
                    price: float, confidence: float = None, metadata: dict = None,
                    timestamp: datetime = None):
        """Save a single trading signal."""
        session = self.get_session()
        try:
            signal = Signal(
                symbol=symbol, strategy_name=strategy_name,
                signal_type=signal_type, price=price,
                confidence=confidence,
                signal_metadata=json.dumps(metadata) if metadata else None,
                timestamp=timestamp or datetime.utcnow(),
            )
            session.add(signal)
            session.commit()
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving signal: {e}")
        finally:
            session.close()

    def save_signals_bulk(self, signals: List[Dict[str, Any]]):
        """Save multiple signals at once."""
        session = self.get_session()
        try:
            for s in signals:
                sig = Signal(
                    symbol=s["symbol"], strategy_name=s["strategy_name"],
                    signal_type=s["signal_type"], price=s["price"],
                    confidence=s.get("confidence"),
                    signal_metadata=json.dumps(s.get("metadata")) if s.get("metadata") else None,
                    timestamp=s.get("timestamp", datetime.utcnow()),
                )
                session.add(sig)
            session.commit()
            _safe_print(f"   [SAVED] Saved {len(signals)} signals.")
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving bulk signals: {e}")
        finally:
            session.close()

    def get_signals(self, symbol: str = None, strategy_name: str = None,
                    limit: int = 100) -> List[Signal]:
        """Retrieve signals with optional filters."""
        session = self.get_session()
        try:
            query = session.query(Signal)
            if symbol:
                query = query.filter(Signal.symbol == symbol)
            if strategy_name:
                query = query.filter(Signal.strategy_name == strategy_name)
            return query.order_by(desc(Signal.timestamp)).limit(limit).all()
        finally:
            session.close()

    # ── Trades ─────────────────────────────────────
    def save_trade(self, symbol: str, side: str, quantity: float, price: float,
                   commission: float, slippage: float, total_cost: float,
                   strategy_name: str, pnl: float = None,
                   timestamp: datetime = None):
        """Save a single executed trade."""
        session = self.get_session()
        try:
            trade = Trade(
                symbol=symbol, side=side, quantity=quantity, price=price,
                commission=commission, slippage=slippage, total_cost=total_cost,
                pnl=pnl, strategy_name=strategy_name,
                timestamp=timestamp or datetime.utcnow(),
            )
            session.add(trade)
            session.commit()
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving trade: {e}")
        finally:
            session.close()

    def get_trades(self, symbol: str = None, strategy_name: str = None,
                   limit: int = 200) -> List[Trade]:
        """Retrieve trades with optional filters."""
        session = self.get_session()
        try:
            query = session.query(Trade)
            if symbol:
                query = query.filter(Trade.symbol == symbol)
            if strategy_name:
                query = query.filter(Trade.strategy_name == strategy_name)
            return query.order_by(desc(Trade.timestamp)).limit(limit).all()
        finally:
            session.close()

    # ── Portfolio ──────────────────────────────────
    def update_portfolio(self, symbol: str, quantity: float, avg_cost: float,
                         current_price: float = None):
        """Insert or update a portfolio position."""
        session = self.get_session()
        try:
            position = session.query(Portfolio).filter_by(symbol=symbol).first()
            current_value = (current_price or avg_cost) * quantity
            unrealized = (current_price - avg_cost) * quantity if current_price else 0

            if position:
                position.quantity = quantity
                position.avg_cost = avg_cost
                position.current_price = current_price
                position.current_value = current_value
                position.unrealized_pnl = unrealized
                position.last_updated = datetime.utcnow()
            else:
                session.add(Portfolio(
                    symbol=symbol, quantity=quantity, avg_cost=avg_cost,
                    current_price=current_price, current_value=current_value,
                    unrealized_pnl=unrealized,
                ))
            session.commit()
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error updating portfolio: {e}")
        finally:
            session.close()

    def get_portfolio(self) -> List[Portfolio]:
        """Get all active portfolio positions."""
        session = self.get_session()
        try:
            return session.query(Portfolio).filter(Portfolio.quantity > 0).all()
        finally:
            session.close()

    def clear_portfolio(self):
        """Clear all portfolio positions."""
        session = self.get_session()
        try:
            session.query(Portfolio).delete()
            session.commit()
        finally:
            session.close()

    # ── Backtest Results ──────────────────────────
    def save_backtest_result(self, result: Dict[str, Any]):
        """Save backtest results to the database."""
        session = self.get_session()
        try:
            bt = BacktestResult(
                strategy_name=result["strategy_name"], symbol=result["symbol"],
                start_date=result["start_date"], end_date=result["end_date"],
                initial_capital=result["initial_capital"], final_value=result["final_value"],
                total_return_pct=result["total_return_pct"],
                sharpe_ratio=result.get("sharpe_ratio"),
                max_drawdown_pct=result.get("max_drawdown_pct"),
                win_rate=result.get("win_rate"),
                total_trades=result["total_trades"],
                winning_trades=result.get("winning_trades"),
                losing_trades=result.get("losing_trades"),
                avg_trade_pnl=result.get("avg_trade_pnl"),
                equity_curve=json.dumps(result.get("equity_curve", [])),
            )
            session.add(bt)
            session.commit()
            _safe_print(f"   [SAVED] Backtest result saved for {result['strategy_name']} on {result['symbol']}.")
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving backtest result: {e}")
        finally:
            session.close()

    def get_backtest_results(self, strategy_name: str = None,
                             symbol: str = None) -> List[BacktestResult]:
        """Retrieve backtest results."""
        session = self.get_session()
        try:
            query = session.query(BacktestResult)
            if strategy_name:
                query = query.filter(BacktestResult.strategy_name == strategy_name)
            if symbol:
                query = query.filter(BacktestResult.symbol == symbol)
            return query.order_by(desc(BacktestResult.created_at)).all()
        finally:
            session.close()

    # ── Risk Events ───────────────────────────────
    def save_risk_event(self, symbol: str, event_type: str, severity: str,
                        message: str, action_taken: str = None,
                        price_at_event: float = None, pnl_at_event: float = None):
        """Save a risk management event."""
        session = self.get_session()
        try:
            event = RiskEvent(
                symbol=symbol, event_type=event_type, severity=severity,
                message=message, action_taken=action_taken,
                price_at_event=price_at_event, pnl_at_event=pnl_at_event,
                timestamp=datetime.utcnow(),
            )
            session.add(event)
            session.commit()
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving risk event: {e}")
        finally:
            session.close()

    def get_risk_events(self, symbol: str = None, limit: int = 50) -> List[RiskEvent]:
        """Retrieve risk events."""
        session = self.get_session()
        try:
            query = session.query(RiskEvent)
            if symbol:
                query = query.filter(RiskEvent.symbol == symbol)
            return query.order_by(desc(RiskEvent.timestamp)).limit(limit).all()
        finally:
            session.close()

    # ── Watchlist ──────────────────────────────────
    def add_to_watchlist(self, user_id: int, symbol: str, notes: str = None):
        """Add symbol to user's watchlist."""
        session = self.get_session()
        try:
            existing = session.query(Watchlist).filter_by(
                user_id=user_id, symbol=symbol).first()
            if not existing:
                session.add(Watchlist(user_id=user_id, symbol=symbol, notes=notes))
                session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()

    def remove_from_watchlist(self, user_id: int, symbol: str):
        """Remove symbol from user's watchlist."""
        session = self.get_session()
        try:
            session.query(Watchlist).filter_by(
                user_id=user_id, symbol=symbol).delete()
            session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()

    def get_watchlist(self, user_id: int) -> List[Watchlist]:
        """Get user's watchlist."""
        session = self.get_session()
        try:
            return session.query(Watchlist).filter_by(user_id=user_id).order_by(
                desc(Watchlist.added_at)).all()
        finally:
            session.close()

    # ── Recommendations ───────────────────────────
    def save_recommendation(self, symbol: str, signal_type: str, confidence: float,
                            reason: str = None, strategy_name: str = None,
                            price_at_signal: float = None, risk_level: str = None):
        """Save a smart pick recommendation."""
        session = self.get_session()
        try:
            rec = Recommendation(
                symbol=symbol, signal_type=signal_type, confidence=confidence,
                reason=reason, strategy_name=strategy_name,
                price_at_signal=price_at_signal, risk_level=risk_level,
                timestamp=datetime.utcnow(),
            )
            session.add(rec)
            session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()

    def get_recommendations(self, limit: int = 20) -> List[Recommendation]:
        """Get recent recommendations."""
        session = self.get_session()
        try:
            return session.query(Recommendation).order_by(
                desc(Recommendation.timestamp)).limit(limit).all()
        finally:
            session.close()

    # ── Analytics ──────────────────────────────────
    def get_performance_summary(self) -> Dict[str, Any]:
        """Compute aggregated performance metrics."""
        session = self.get_session()
        try:
            total_trades = session.query(func.count(Trade.id)).scalar() or 0
            total_pnl = session.query(func.sum(Trade.pnl)).scalar() or 0.0
            avg_pnl = session.query(func.avg(Trade.pnl)).filter(Trade.pnl.isnot(None)).scalar() or 0.0
            winning = session.query(func.count(Trade.id)).filter(Trade.pnl > 0).scalar() or 0
            losing = session.query(func.count(Trade.id)).filter(Trade.pnl < 0).scalar() or 0
            total_signals = session.query(func.count(Signal.id)).scalar() or 0

            return {
                "total_trades": total_trades,
                "total_pnl": round(total_pnl, 2),
                "avg_pnl_per_trade": round(avg_pnl, 2),
                "winning_trades": winning,
                "losing_trades": losing,
                "win_rate": round(winning / total_trades * 100, 2) if total_trades > 0 else 0,
                "total_signals": total_signals,
            }
        finally:
            session.close()

    # ── Broker State ──────────────────────────────
    def save_broker_state(self, user_id: int, broker_type: str, is_connected: bool,
                          cash: float, initial_capital: float,
                          positions: dict, daily_pnl: float = 0.0):
        """Save or update broker state for persistence across refreshes."""
        session = self.get_session()
        try:
            state = session.query(BrokerState).filter_by(user_id=user_id).first()
            pos_json = json.dumps(positions)
            if state:
                state.broker_type = broker_type
                state.is_connected = 1 if is_connected else 0
                state.cash = cash
                state.initial_capital = initial_capital
                state.positions_json = pos_json
                state.daily_pnl = daily_pnl
                state.updated_at = datetime.utcnow()
            else:
                session.add(BrokerState(
                    user_id=user_id, broker_type=broker_type,
                    is_connected=1 if is_connected else 0,
                    cash=cash, initial_capital=initial_capital,
                    positions_json=pos_json, daily_pnl=daily_pnl,
                ))
            session.commit()
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving broker state: {e}")
        finally:
            session.close()

    def get_broker_state(self, user_id: int) -> Optional[Dict]:
        """Retrieve persisted broker state."""
        session = self.get_session()
        try:
            state = session.query(BrokerState).filter_by(user_id=user_id).first()
            if not state:
                return None
            return {
                "broker_type": state.broker_type,
                "is_connected": bool(state.is_connected),
                "cash": state.cash,
                "initial_capital": state.initial_capital,
                "positions": json.loads(state.positions_json) if state.positions_json else {},
                "daily_pnl": state.daily_pnl,
            }
        finally:
            session.close()

    def clear_broker_state(self, user_id: int):
        """Delete persisted broker state (on disconnect)."""
        session = self.get_session()
        try:
            session.query(BrokerState).filter_by(user_id=user_id).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    # ── Auto-Trade Config ─────────────────────────
    def save_auto_trade_config(self, user_id: int, is_active: bool,
                                strategy_name: str, symbols: list,
                                interval_minutes: int = 15,
                                max_position_pct: float = 0.2,
                                stop_loss_pct: float = None,
                                take_profit_pct: float = None,
                                market_hours_only: bool = True):
        """Save auto-trade configuration to DB for daemon to read."""
        session = self.get_session()
        try:
            cfg = session.query(AutoTradeConfig).filter_by(user_id=user_id).first()
            symbols_json = json.dumps(symbols)
            if cfg:
                cfg.is_active = 1 if is_active else 0
                cfg.strategy_name = strategy_name
                cfg.symbols = symbols_json
                cfg.interval_minutes = interval_minutes
                cfg.max_position_pct = max_position_pct
                cfg.stop_loss_pct = stop_loss_pct
                cfg.take_profit_pct = take_profit_pct
                cfg.market_hours_only = 1 if market_hours_only else 0
                cfg.updated_at = datetime.utcnow()
            else:
                session.add(AutoTradeConfig(
                    user_id=user_id, is_active=1 if is_active else 0,
                    strategy_name=strategy_name, symbols=symbols_json,
                    interval_minutes=interval_minutes,
                    max_position_pct=max_position_pct,
                    stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
                    market_hours_only=1 if market_hours_only else 0,
                ))
            session.commit()
        except Exception as e:
            session.rollback()
            _safe_print(f"   [ERROR] Error saving auto-trade config: {e}")
        finally:
            session.close()

    def get_auto_trade_config(self, user_id: int) -> Optional[Dict]:
        """Retrieve auto-trade config from DB."""
        session = self.get_session()
        try:
            cfg = session.query(AutoTradeConfig).filter_by(user_id=user_id).first()
            if not cfg:
                return None
            return {
                "is_active": bool(cfg.is_active),
                "strategy_name": cfg.strategy_name,
                "symbols": json.loads(cfg.symbols) if cfg.symbols else [],
                "interval_minutes": cfg.interval_minutes,
                "max_position_pct": cfg.max_position_pct,
                "stop_loss_pct": cfg.stop_loss_pct,
                "take_profit_pct": cfg.take_profit_pct,
                "market_hours_only": bool(cfg.market_hours_only),
                "last_run": cfg.last_run,
            }
        finally:
            session.close()

    def set_auto_trade_active(self, user_id: int, active: bool):
        """Toggle auto-trade active flag (used by daemon to check if should stop)."""
        session = self.get_session()
        try:
            cfg = session.query(AutoTradeConfig).filter_by(user_id=user_id).first()
            if cfg:
                cfg.is_active = 1 if active else 0
                cfg.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def update_auto_trade_last_run(self, user_id: int):
        """Update last_run timestamp for auto-trade config."""
        session = self.get_session()
        try:
            cfg = session.query(AutoTradeConfig).filter_by(user_id=user_id).first()
            if cfg:
                cfg.last_run = datetime.utcnow()
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
