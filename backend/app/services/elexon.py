"""
Thin client for the two Elexon BMRS datasets we need.

Responsibilities:
  1. Call the public Elexon API (no key needed).
  2. Convert raw JSON into our own ActualPoint / ForecastPoint objects.
  3. Cache results in memory so the dashboard stays fast and we don't hit
     Elexon on every slider move.
"""

import logging
import time
from datetime import datetime, timedelta
from threading import Lock

import httpx

from .. import config
from ..core.models import ActualPoint, ForecastPoint

logger = logging.getLogger(__name__)


def _parse_time(value: str) -> datetime:
    """Elexon returns ISO-8601 strings ending in 'Z' (UTC)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class ElexonClient:
    """Fetches and caches wind actuals and forecasts."""

    def __init__(self, base_url: str = config.ELEXON_BASE_URL,
                 ttl_seconds: int = config.CACHE_TTL_SECONDS):
        self.base_url = base_url
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, list]] = {}
        self._lock = Lock()  # avoid duplicate fetches from parallel requests

    # ---- public API --------------------------------------------------------

    def get_actuals(self, start: datetime, end: datetime) -> list[ActualPoint]:
        """Actual national wind generation with start_time in [start, end)."""
        key = f"actuals:{_iso(start)}:{_iso(end)}"
        return self._cached(key, lambda: self._fetch_actuals(start, end))

    def get_forecasts(self, publish_from: datetime,
                      publish_to: datetime) -> list[ForecastPoint]:
        """All wind forecasts published in [publish_from, publish_to]."""
        key = f"forecasts:{_iso(publish_from)}:{_iso(publish_to)}"
        return self._cached(key, lambda: self._fetch_forecasts(publish_from, publish_to))

    # ---- internals ---------------------------------------------------------

    def _cached(self, key: str, loader):
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.time() - hit[0] < self.ttl_seconds:
                return hit[1]
            data = loader()
            self._cache[key] = (time.time(), data)
            return data

    def _get_json(self, dataset: str, params: dict) -> list[dict]:
        url = f"{self.base_url}/{dataset}/stream"
        logger.info("Fetching %s %s", dataset, params)
        response = httpx.get(url, params=params, timeout=config.HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()

    def _fetch_actuals(self, start: datetime, end: datetime) -> list[ActualPoint]:
        # FUELHH is filtered by publish time. Each half-hour is published at
        # the END of its period, so we widen the window slightly and then
        # filter precisely on start_time.
        raw = self._get_json(config.ACTUALS_DATASET, {
            "publishDateTimeFrom": _iso(start),
            "publishDateTimeTo": _iso(end + timedelta(hours=1)),
            "fuelType": config.WIND_FUEL_TYPE,
        })
        points = [
            ActualPoint(start_time=_parse_time(r["startTime"]),
                        generation_mw=float(r["generation"]))
            for r in raw
            if r.get("fuelType") == config.WIND_FUEL_TYPE
        ]
        return [p for p in points if start <= p.start_time < end]

    def _fetch_forecasts(self, publish_from: datetime,
                         publish_to: datetime) -> list[ForecastPoint]:
        raw = self._get_json(config.FORECAST_DATASET, {
            "publishDateTimeFrom": _iso(publish_from),
            "publishDateTimeTo": _iso(publish_to),
        })
        points = [
            ForecastPoint(start_time=_parse_time(r["startTime"]),
                          publish_time=_parse_time(r["publishTime"]),
                          generation_mw=float(r["generation"]))
            for r in raw
        ]
        # Drop "forecasts" for hours that had already started when published:
        # they are not useful for a purchase decision.
        return [p for p in points if p.horizon_hours >= 0]


# One shared client per process (keeps the cache warm between requests).
elexon_client = ElexonClient()
