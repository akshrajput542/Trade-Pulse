"""
Abstract base class for all trading strategies.
Every strategy must implement `generate_signals()`.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd


class Strategy(ABC):
    """Base class for all trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Strategy parameters dict for logging/display."""
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals from OHLCV data.

        Args:
            df: DataFrame with at least Open, High, Low, Close, Volume columns
                indexed by Date.

        Returns:
            DataFrame with an added 'Signal' column containing:
                1  = BUY
               -1  = SELL
                0  = HOLD
            And optionally other indicator columns used by the strategy.
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}({self.parameters})>"
