"""
Core business logic: which forecast would the trader have actually seen?

The client buys power on the day-ahead market, so for every delivery hour
they can only use forecasts that were published *before* their decision.
We model that with a "horizon" H (hours):

    usable forecast = the most recent forecast published at least H hours
                      before the delivery time.

These functions are pure (no I/O), which keeps them fast and easy to test.
"""

from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable

from .models import ActualPoint, ComparisonPoint, ForecastPoint


def latest_forecasts_for_horizon(
    forecasts: Iterable[ForecastPoint],
    horizon_hours: float,
) -> dict[datetime, ForecastPoint]:
    """
    For each delivery time, pick the latest forecast published at least
    `horizon_hours` before it.

    Returns a mapping: delivery start_time -> chosen ForecastPoint.
    Delivery times with no qualifying forecast are simply left out.
    """
    horizon = timedelta(hours=horizon_hours)

    # Group every forecast by the hour it predicts.
    by_target: dict[datetime, list[ForecastPoint]] = defaultdict(list)
    for point in forecasts:
        by_target[point.start_time].append(point)

    chosen: dict[datetime, ForecastPoint] = {}
    for target_time, candidates in by_target.items():
        cutoff = target_time - horizon

        # Sort by publish time once, then binary-search for the cutoff.
        candidates.sort(key=lambda p: p.publish_time)
        publish_times = [p.publish_time for p in candidates]
        idx = bisect_right(publish_times, cutoff)  # first index AFTER cutoff

        if idx > 0:
            chosen[target_time] = candidates[idx - 1]

    return chosen


def build_comparison(
    actuals: Iterable[ActualPoint],
    forecasts: Iterable[ForecastPoint],
    horizon_hours: float,
    start: datetime,
    end: datetime,
) -> list[ComparisonPoint]:
    """
    Pair each actual value in [start, end) with the forecast that would have
    been available `horizon_hours` earlier.

    Forecasts are hourly while actuals are half-hourly, so we compare on the
    hourly timestamps where both exist.
    """
    chosen = latest_forecasts_for_horizon(forecasts, horizon_hours)

    rows: list[ComparisonPoint] = []
    for actual in actuals:
        if not (start <= actual.start_time < end):
            continue
        forecast = chosen.get(actual.start_time)
        if forecast is None:
            continue
        rows.append(
            ComparisonPoint(
                start_time=actual.start_time,
                actual_mw=actual.generation_mw,
                forecast_mw=forecast.generation_mw,
                publish_time=forecast.publish_time,
            )
        )

    rows.sort(key=lambda r: r.start_time)
    return rows
