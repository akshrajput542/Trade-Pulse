"""
Zerodha Kite Connect broker integration.

Requires: Zerodha account + Kite Connect API subscription
Set credentials in .env: ZERODHA_API_KEY, ZERODHA_API_SECRET, etc.
"""

from datetime import datetime
from typing import List
import logging
from .base import BrokerBase, OrderResult, Position, AccountInfo

logger = logging.getLogger("TradePulse.Zerodha")


class ZerodhaBroker(BrokerBase):
    """Zerodha Kite Connect broker."""

    def __init__(self):
        self._connected = False
        self._kite = None
        self._access_token = None

    @property
    def name(self) -> str:
        return "Zerodha Kite"

    @property
    def is_live(self) -> bool:
        return True

    def connect(self, api_key="", api_secret="", request_token="", **kw) -> bool:
        import config
        api_key = api_key or config.ZERODHA_API_KEY
        api_secret = api_secret or config.ZERODHA_API_SECRET
        if not api_key or not api_secret:
            logger.error("Zerodha API key/secret not configured")
            return False
        try:
            from kiteconnect import KiteConnect
            self._kite = KiteConnect(api_key=api_key)
            if request_token:
                data = self._kite.generate_session(request_token, api_secret=api_secret)
                self._access_token = data["access_token"]
                self._kite.set_access_token(self._access_token)
                self._connected = True
                return True
            else:
                logger.warning(f"Login URL: {self._kite.login_url()}")
                return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        self._connected = False
        self._kite = None

    def is_connected(self) -> bool:
        if not self._connected or not self._kite:
            return False
        try:
            self._kite.profile()
            return True
        except Exception:
            self._connected = False
            return False

    def get_account_info(self) -> AccountInfo:
        if not self._connected:
            return AccountInfo(broker_name=self.name)
        try:
            m = self._kite.margins("equity")
            avail = m.get("available", {}).get("live_balance", 0)
            return AccountInfo(broker_name=self.name, is_connected=True,
                               available_cash=round(avail, 2),
                               total_value=round(avail, 2))
        except Exception:
            return AccountInfo(broker_name=self.name, is_connected=True)

    def place_order(self, symbol, side, quantity, order_type="MARKET",
                    price=0.0, trigger_price=0.0) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, symbol=symbol, side=side,
                               message="Not connected")
        try:
            tsym = symbol.replace(".NS", "")
            params = dict(tradingsymbol=tsym, exchange="NSE",
                          transaction_type=side, quantity=quantity,
                          order_type=order_type, product="CNC", variety="regular")
            if price > 0 and order_type in ("LIMIT", "SL"):
                params["price"] = price
            if trigger_price > 0:
                params["trigger_price"] = trigger_price
            oid = self._kite.place_order(**params)
            return OrderResult(success=True, order_id=str(oid), symbol=symbol,
                               side=side, quantity=quantity, price=price,
                               status="PENDING", message="Order placed")
        except Exception as e:
            return OrderResult(success=False, symbol=symbol, side=side, message=str(e))

    def get_positions(self) -> List[Position]:
        if not self._connected:
            return []
        try:
            holdings = self._kite.holdings()
            return [Position(
                symbol=f"{h['tradingsymbol']}.NS",
                quantity=h.get("quantity", 0),
                avg_cost=h.get("average_price", 0),
                current_price=h.get("last_price", 0),
                pnl=round((h.get("last_price", 0) - h.get("average_price", 0)) * h.get("quantity", 0), 2),
            ) for h in holdings if h.get("quantity", 0) > 0]
        except Exception:
            return []

    def get_live_price(self, symbol) -> float:
        if not self._connected:
            return 0.0
        try:
            tsym = symbol.replace(".NS", "")
            q = self._kite.ltp(f"NSE:{tsym}")
            return q.get(f"NSE:{tsym}", {}).get("last_price", 0.0)
        except Exception:
            return 0.0

    def cancel_order(self, order_id) -> bool:
        if not self._connected:
            return False
        try:
            self._kite.cancel_order(variety="regular", order_id=order_id)
            return True
        except Exception:
            return False
