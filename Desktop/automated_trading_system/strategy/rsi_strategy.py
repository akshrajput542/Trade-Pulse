"""
RSI (Relative Strength Index) Strategy.

BUY  when RSI drops below the oversold threshold (default 30).
SELL when RSI rises above the overbought threshold (default 70).
"""

import pandas as pd
from typing import Dict, Any

from .base import Strategy
from data.indicators import TechnicalIndicators
import config


class RSIStrategy(Strategy):
    """RSI-based overbought/oversold strategy."""

    def __init__(self, period: int = None, oversold: int = None, overbought: int = None):
        self.period = period or config.RSI_PERIOD
        self.oversold = oversold or config.RSI_OVERSOLD
        self.overbought = overbought or config.RSI_OVERBOUGHT

    @property
    def name(self) -> str:
        return f"RSI_{self.period}_{self.oversold}_{self.overbought}"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "oversold": self.oversold,
            "overbought": self.overbought,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate RSI-based signals.

        Returns DataFrame with columns:
            RSI, Signal
        """
        result = df.copy()

        # Compute RSI
        result["RSI"] = TechnicalIndicators.compute_rsi(df, period=self.period)

        result["Signal"] = 0

        # BUY when RSI crosses below oversold from above
        result.loc[
            (result["RSI"] < self.oversold) &
            (result["RSI"].shift(1) >= self.oversold),
            "Signal"
        ] = 1  # BUY

        # SELL when RSI crosses above overbought from below
        result.loc[
            (result["RSI"] > self.overbought) &
            (result["RSI"].shift(1) <= self.overbought),
            "Signal"
        ] = -1  # SELL

        return result
