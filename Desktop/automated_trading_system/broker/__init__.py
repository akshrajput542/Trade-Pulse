"""Broker integration layer — abstract interface + implementations."""
from .base import BrokerBase
from .paper import PaperBroker

__all__ = ["BrokerBase", "PaperBroker"]


def get_broker(broker_type: str = None, **kwargs):
    """Factory: return broker instance by type string."""
    import config
    broker_type = broker_type or config.BROKER_TYPE

    if broker_type == "paper":
        return PaperBroker(**kwargs)
    elif broker_type == "zerodha":
        from .zerodha import ZerodhaBroker
        return ZerodhaBroker(**kwargs)
    elif broker_type == "angel":
        from .angel import AngelBroker
        return AngelBroker(**kwargs)
    else:
        return PaperBroker(**kwargs)
