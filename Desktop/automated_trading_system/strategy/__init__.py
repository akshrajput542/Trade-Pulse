"""Signal generation layer — strategy base class and implementations."""
from .base import Strategy
from .sma_crossover import SMACrossoverStrategy
from .rsi_strategy import RSIStrategy
from .macd_strategy import MACDStrategy
from .bollinger_strategy import BollingerStrategy
from .supertrend_strategy import SuperTrendStrategy
from .combined_strategy import CombinedStrategy

STRATEGIES = {
    "sma": SMACrossoverStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
    "supertrend": SuperTrendStrategy,
    "smart_auto": CombinedStrategy,
}

__all__ = [
    "Strategy", "SMACrossoverStrategy", "RSIStrategy", "MACDStrategy",
    "BollingerStrategy", "SuperTrendStrategy", "CombinedStrategy",
    "STRATEGIES",
]
