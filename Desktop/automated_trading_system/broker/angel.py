"""
Angel One SmartAPI broker integration.

Requires: Angel One demat account + SmartAPI app
Set credentials in .env: ANGEL_API_KEY, ANGEL_CLIENT_ID, etc.
"""

from datetime import datetime
from typing import List
import logging
from .base import BrokerBase, OrderResult, Position, AccountInfo

logger = logging.getLogger("TradePulse.Angel")


class AngelBroker(BrokerBase):
    """Angel One SmartAPI broker."""

    def __init__(self):
        self._connected = False
        self._obj = None

    @property
    def name(self) -> str:
        return "Angel One"

    @property
    def is_live(self) -> bool:
        return True

    def connect(self, api_key="", client_id="", password="",
                totp_secret="", **kw) -> bool:
        import config
        api_key = api_key or config.ANGEL_API_KEY
        client_id = client_id or config.ANGEL_CLIENT_ID
        password = password or config.ANGEL_PASSWORD
        totp_secret = totp_secret or config.ANGEL_TOTP_SECRET
        if not all([api_key, client_id, password]):
            logger.error("Angel credentials not configured")
            return False
        try:
            from SmartApi import SmartConnect
            import pyotp
            self._obj = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_secret).now() if totp_secret else ""
            data = self._obj.generateSession(client_id, password, totp)
            if data.get("status"):
                self._connected = True
                return True
            logger.error(f"Angel login failed: {data.get('message')}")
            return False
        except ImportError:
            logger.error("SmartApi not installed. Run: pip install smartapi-python")
            return False
        except Exception as e:
            logger.error(f"Angel connection failed: {e}")
            return False

    def disconnect(self):
        if self._obj:
            try:
                self._obj.terminateSession(self._obj.userId)
            except Exception:
                pass
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account_info(self) -> AccountInfo:
        if not self._connected:
            return AccountInfo(broker_name=self.name)
        try:
            rms = self._obj.rmsLimit()
            avail = float(rms.get("data", {}).get("availablecash", 0))
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
            params = {
                "variety": "NORMAL",
                "tradingsymbol": tsym,
                "symboltoken": "",  # Would need token lookup
                "transactiontype": side,
                "exchange": "NSE",
                "ordertype": order_type,
                "producttype": "DELIVERY",
                "duration": "DAY",
                "quantity": str(quantity),
            }
            if price > 0:
                params["price"] = str(price)
            resp = self._obj.placeOrder(params)
            if resp:
                return OrderResult(success=True, order_id=str(resp),
                                   symbol=symbol, side=side, quantity=quantity,
                                   price=price, status="PENDING",
                                   message="Order placed")
            return OrderResult(success=False, symbol=symbol, side=side,
                               message="Order rejected")
        except Exception as e:
            return OrderResult(success=False, symbol=symbol, side=side,
                               message=str(e))

    def get_positions(self) -> List[Position]:
        if not self._connected:
            return []
        try:
            holdings = self._obj.holding()
            if not holdings.get("data"):
                return []
            return [Position(
                symbol=f"{h['tradingsymbol']}.NS",
                quantity=int(h.get("quantity", 0)),
                avg_cost=float(h.get("averageprice", 0)),
                current_price=float(h.get("ltp", 0)),
                pnl=float(h.get("profitandloss", 0)),
            ) for h in holdings["data"] if int(h.get("quantity", 0)) > 0]
        except Exception:
            return []

    def get_live_price(self, symbol) -> float:
        if not self._connected:
            return 0.0
        try:
            tsym = symbol.replace(".NS", "")
            data = self._obj.ltpData("NSE", tsym, "")
            return float(data.get("data", {}).get("ltp", 0))
        except Exception:
            return 0.0

    def cancel_order(self, order_id) -> bool:
        if not self._connected:
            return False
        try:
            self._obj.cancelOrder(order_id, "NORMAL")
            return True
        except Exception:
            return False
