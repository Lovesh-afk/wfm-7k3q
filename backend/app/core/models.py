"""
Plain data classes used across the backend.

They keep the domain logic independent of the Elexon JSON format and of
FastAPI, which makes the core functions easy to unit test.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActualPoint:
    """Measured wind generation for one half-hour settlement period."""
    start_time: datetime   # start of the settlement period (UTC)
    generation_mw: float


@dataclass(frozen=True)
class ForecastPoint:
    """One forecast value: what was predicted for start_time, and when."""
    start_time: datetime    # the delivery hour being forecast (UTC)
    publish_time: datetime  # when this forecast was published (UTC)
    generation_mw: float

    @property
    def horizon_hours(self) -> float:
        """How far ahead of delivery this forecast was made."""
        return (self.start_time - self.publish_time).total_seconds() / 3600


@dataclass(frozen=True)
class ComparisonPoint:
    """An actual value paired with the forecast that would have been used."""
    start_time: datetime
    actual_mw: float
    forecast_mw: float
    publish_time: datetime

    @property
    def error_mw(self) -> float:
        """Forecast minus actual. Positive = forecast was too high."""
        return self.forecast_mw - self.actual_mw

    @property
    def horizon_hours(self) -> float:
        return (self.start_time - self.publish_time).total_seconds() / 3600
