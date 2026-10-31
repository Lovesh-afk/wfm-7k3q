"""
HTTP endpoints consumed by the React frontend.

The two business questions map to two groups of endpoints:

  1. "What is the latest forecast I can use right now?"
       GET /api/forecast-at  -> latest forecast available at a decision time,
                                with an expected-error band.

  2. "How accurate are these forecasts?"
       GET /api/analysis      -> actual vs forecast series + headline metrics
       GET /api/horizon-curve -> how accuracy changes with forecast horizon
"""

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import config
from ..core import metrics
from ..core.forecast import build_comparison
from ..core.models import ActualPoint, ForecastPoint
from ..services.elexon import ElexonClient, elexon_client

router = APIRouter(prefix="/api")

HORIZON_CURVE_STEP_HOURS = 3


# ---- helpers ---------------------------------------------------------------

def get_client() -> ElexonClient:
    """FastAPI dependency (overridden with a fake client in tests)."""
    return elexon_client


def _load_month(client: ElexonClient) -> tuple[list[ActualPoint], list[ForecastPoint]]:
    """Fetch all data needed for January 2026 (cached after the first call)."""
    try:
        actuals = client.get_actuals(config.TARGET_START, config.TARGET_END)
        forecasts = client.get_forecasts(
            config.TARGET_START - config.FORECAST_LOOKBACK, config.TARGET_END
        )
    except Exception as exc:  # network errors, Elexon downtime, etc.
        raise HTTPException(status_code=502,
                            detail=f"Could not load data from Elexon: {exc}") from exc
    return actuals, forecasts


def _date_range(start: date, end: date) -> tuple[datetime, datetime]:
    """Convert inclusive dates into a UTC [start, end) datetime window,
    clamped to January 2026."""
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    start_dt = max(datetime.combine(start, time.min, tzinfo=timezone.utc), config.TARGET_START)
    end_dt = min(datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc),
                 config.TARGET_END)
    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="Dates must be within January 2026")
    return start_dt, end_dt


_p90_cache: dict[int, dict[int, float]] = {}


def _p90_by_horizon(actuals: list[ActualPoint],
                    forecasts: list[ForecastPoint]) -> dict[int, float]:
    """Month-wide P90 absolute error for each horizon step (0, 3, ... 48h).

    It only depends on the loaded data, so we compute it once per dataset
    (keyed by the list's identity, which changes when the cache refreshes).
    """
    key = id(forecasts)
    if key not in _p90_cache:
        _p90_cache.clear()
        _p90_cache[key] = {
            h: metrics.summary_metrics(
                build_comparison(actuals, forecasts, h,
                                 config.TARGET_START, config.TARGET_END)
            )["p90_abs_error"] or 0
            for h in range(0, config.MAX_HORIZON_HOURS + 1, HORIZON_CURVE_STEP_HOURS)
        }
    return _p90_cache[key]


HorizonParam = Query(config.DEFAULT_HORIZON_HOURS,
                     ge=config.MIN_HORIZON_HOURS, le=config.MAX_HORIZON_HOURS,
                     description="Forecast must be published at least this many hours ahead")


# ---- endpoints -------------------------------------------------------------

@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/analysis")
def analysis(
    start: date = Query(date(2026, 1, 1)),
    end: date = Query(date(2026, 1, 31)),
    horizon: float = HorizonParam,
    client: ElexonClient = Depends(get_client),
) -> dict:
    """Actual vs forecast for every hour in the range, plus accuracy metrics."""
    start_dt, end_dt = _date_range(start, end)
    actuals, forecasts = _load_month(client)
    rows = build_comparison(actuals, forecasts, horizon, start_dt, end_dt)

    return {
        "horizon_hours": horizon,
        "summary": metrics.summary_metrics(rows),
        "by_hour": metrics.error_by_hour_of_day(rows),
        "distribution": metrics.error_distribution(rows),
        "series": [
            {
                "time": r.start_time.isoformat(),
                "actual": r.actual_mw,
                "forecast": r.forecast_mw,
                "error": round(r.error_mw, 1),
                "published": r.publish_time.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/horizon-curve")
def horizon_curve(
    start: date = Query(date(2026, 1, 1)),
    end: date = Query(date(2026, 1, 31)),
    client: ElexonClient = Depends(get_client),
) -> list[dict]:
    """Accuracy at each horizon (0h, 3h, ... 48h) to show how error grows
    the further ahead you forecast."""
    start_dt, end_dt = _date_range(start, end)
    actuals, forecasts = _load_month(client)

    curve = []
    for h in range(config.MIN_HORIZON_HOURS, config.MAX_HORIZON_HOURS + 1,
                   HORIZON_CURVE_STEP_HOURS):
        s = metrics.summary_metrics(build_comparison(actuals, forecasts, h, start_dt, end_dt))
        curve.append({"horizon": h, "mae": s["mae"], "rmse": s["rmse"],
                      "p90_abs_error": s["p90_abs_error"], "bias": s["bias"]})
    return curve


@router.get("/forecast-at")
def forecast_at(
    decision_time: datetime = Query(datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
                                    description="When the trader makes the decision (UTC)"),
    hours_ahead: int = Query(48, ge=1, le=60),
    client: ElexonClient = Depends(get_client),
) -> dict:
    """
    The forecast a trader would see at `decision_time`: the most recent
    forecast run published at or before that moment, for the next
    `hours_ahead` hours. Each point carries an expected-error band (P90 of
    historical absolute error at that horizon) and, for hindsight, the actual.
    """
    if decision_time.tzinfo is None:
        decision_time = decision_time.replace(tzinfo=timezone.utc)

    actuals, forecasts = _load_month(client)

    published = [f.publish_time for f in forecasts if f.publish_time <= decision_time]
    if not published:
        raise HTTPException(status_code=404, detail="No forecast published before that time")
    latest_publish = max(published)

    window_end = decision_time + timedelta(hours=hours_ahead)
    run = sorted(
        (f for f in forecasts
         if f.publish_time == latest_publish and decision_time <= f.start_time < window_end),
        key=lambda f: f.start_time,
    )

    p90_by_horizon = _p90_by_horizon(actuals, forecasts)

    def band_for(horizon_h: float) -> float:
        nearest = min(p90_by_horizon, key=lambda h: abs(h - horizon_h))
        return p90_by_horizon[nearest]

    actual_by_time = {a.start_time: a.generation_mw for a in actuals}

    return {
        "decision_time": decision_time.isoformat(),
        "forecast_published": latest_publish.isoformat(),
        "points": [
            {
                "time": f.start_time.isoformat(),
                "forecast": f.generation_mw,
                "band": round(band_for(f.horizon_hours), 1),
                "horizon_hours": round(f.horizon_hours, 1),
                "actual": actual_by_time.get(f.start_time),
            }
            for f in run
        ],
    }
