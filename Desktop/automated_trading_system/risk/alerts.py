"""
Risk alert system — logs risk events and provides notifications.
"""

from datetime import datetime
from dataclasses import dataclass, field
from typing import List


@dataclass
class RiskAlert:
    """A single risk event/alert."""
    timestamp: datetime = field(default_factory=datetime.now)
    symbol: str = ""
    alert_type: str = ""     # STOP_LOSS, TRAILING_STOP, TAKE_PROFIT, MAX_LOSS, POSITION_LIMIT
    severity: str = "info"   # info, warning, danger
    message: str = ""
    action_taken: str = ""   # e.g., "Position closed", "Trade blocked"


class RiskAlertManager:
    """Manages risk alerts for display in dashboard."""

    def __init__(self, max_alerts: int = 100):
        self._alerts: List[RiskAlert] = []
        self._max = max_alerts

    def add_alert(self, symbol: str, alert_type: str, severity: str,
                  message: str, action_taken: str = ""):
        alert = RiskAlert(
            symbol=symbol, alert_type=alert_type,
            severity=severity, message=message,
            action_taken=action_taken,
        )
        self._alerts.insert(0, alert)
        if len(self._alerts) > self._max:
            self._alerts = self._alerts[:self._max]

    def get_alerts(self, limit: int = 20) -> List[RiskAlert]:
        return self._alerts[:limit]

    def get_danger_alerts(self, limit: int = 10) -> List[RiskAlert]:
        return [a for a in self._alerts if a.severity == "danger"][:limit]

    def clear(self):
        self._alerts.clear()

    @property
    def count(self) -> int:
        return len(self._alerts)

    @property
    def danger_count(self) -> int:
        return sum(1 for a in self._alerts if a.severity == "danger")
