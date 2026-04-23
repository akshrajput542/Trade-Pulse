"""
SuperTrend Strategy — popular trend-following indicator in Indian markets.

BUY  when price crosses above SuperTrend line (trend turns bullish).
SELL when price crosses below SuperTrend line (trend turns bearish).

Very beginner-friendly — gives clear, unambiguous signals.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from .base import Strategy
from data.indicators import TechnicalIndicators
import config


class SuperTrendStrategy(Strategy):
    """SuperTrend indicator strategy."""

    def __init__(self, period: int = None, multiplier: float = None):
        self.period = period or config.SUPERTREND_PERIOD
        self.multiplier = multiplier or config.SUPERTREND_MULTIPLIER

    @property
    def name(self) -> str:
        return f"SuperTrend_{self.period}_{self.multiplier}"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"period": self.period, "multiplier": self.multiplier}

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        st = TechnicalIndicators.compute_supertrend(
            df, period=self.period, multiplier=self.multiplier
        )
        result["SuperTrend"] = st["SuperTrend"]
        result["ST_Direction"] = st["Direction"]

        result["Signal"] = 0

        # BUY when direction changes from -1 to 1 (bearish to bullish)
        result.loc[
            (result["ST_Direction"] == 1) &
            (result["ST_Direction"].shift(1) == -1),
            "Signal"
        ] = 1

        # SELL when direction changes from 1 to -1 (bullish to bearish)
        result.loc[
            (result["ST_Direction"] == -1) &
            (result["ST_Direction"].shift(1) == 1),
            "Signal"
        ] = -1

        return result
