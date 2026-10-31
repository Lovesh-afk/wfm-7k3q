"""Unit tests for the forecast-selection and metrics logic (no network)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.forecast import build_comparison, latest_forecasts_for_horizon
from app.core.metrics import error_by_hour_of_day, summary_metrics
from app.core.models import ActualPoint, ForecastPoint

UTC = timezone.utc
T = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)  # a delivery hour


def fc(publish_hours_before: float, value: float, target: datetime = T) -> ForecastPoint:
    return ForecastPoint(start_time=target,
                         publish_time=target - timedelta(hours=publish_hours_before),
                         generation_mw=value)


def test_picks_latest_forecast_respecting_horizon():
    forecasts = [fc(30, 1000), fc(26, 1100), fc(20, 1200), fc(2, 1300)]

    # With a 24h horizon, only forecasts published >= 24h before are allowed;
    # the latest of those is the one published 26h before.
    chosen = latest_forecasts_for_horizon(forecasts, horizon_hours=24)
    assert chosen[T].generation_mw == 1100

    # With a 0h horizon the most recent forecast wins.
    assert latest_forecasts_for_horizon(forecasts, 0)[T].generation_mw == 1300


def test_forecast_published_exactly_at_cutoff_is_allowed():
    chosen = latest_forecasts_for_horizon([fc(24, 999)], horizon_hours=24)
    assert chosen[T].generation_mw == 999


def test_no_qualifying_forecast_means_target_is_skipped():
    chosen = latest_forecasts_for_horizon([fc(5, 500)], horizon_hours=24)
    assert T not in chosen


def test_build_comparison_pairs_actuals_and_filters_range():
    t2 = T + timedelta(hours=1)
    actuals = [
        ActualPoint(T, 1000),
        ActualPoint(T + timedelta(minutes=30), 1050),  # half-hour: no forecast
        ActualPoint(t2, 2000),
        ActualPoint(T - timedelta(days=5), 3000),      # outside range
    ]
    forecasts = [fc(25, 1200), fc(25, 1800, target=t2)]

    rows = build_comparison(actuals, forecasts, 24, start=T, end=T + timedelta(days=1))

    assert [r.start_time for r in rows] == [T, t2]
    assert rows[0].error_mw == 200    # forecast too high
    assert rows[1].error_mw == -200   # forecast too low


def test_summary_metrics_values():
    actuals = [ActualPoint(T + timedelta(hours=i), 1000) for i in range(4)]
    errors = [100, -100, 300, -300]
    forecasts = [fc(25, 1000 + e, target=T + timedelta(hours=i)) for i, e in enumerate(errors)]
    rows = build_comparison(actuals, forecasts, 24, T, T + timedelta(days=1))

    s = summary_metrics(rows)
    assert s["count"] == 4
    assert s["mae"] == 200
    assert s["bias"] == 0
    assert s["rmse"] == pytest.approx(223.6, abs=0.1)
    assert s["mape"] == 20.0
    assert s["max_abs_error"] == 300
    assert s["mae_bias_corrected"] == 200  # bias is 0, so nothing to remove


def test_bias_corrected_mae_removes_systematic_offset():
    # Every forecast is exactly 500 MW too high: MAE 500, but after removing
    # the bias the forecast is perfect.
    actuals = [ActualPoint(T + timedelta(hours=i), 1000) for i in range(3)]
    forecasts = [fc(25, 1500, target=T + timedelta(hours=i)) for i in range(3)]
    s = summary_metrics(build_comparison(actuals, forecasts, 24, T, T + timedelta(days=1)))
    assert s["mae"] == 500 and s["bias"] == 500
    assert s["mae_bias_corrected"] == 0


def test_summary_metrics_empty():
    assert summary_metrics([])["mae"] is None


def test_error_by_hour_groups_by_utc_hour():
    actuals = [ActualPoint(T, 1000), ActualPoint(T + timedelta(days=1), 1000)]
    forecasts = [fc(25, 1100), fc(25, 1300, target=T + timedelta(days=1))]
    rows = build_comparison(actuals, forecasts, 24, T, T + timedelta(days=2))

    by_hour = error_by_hour_of_day(rows)
    assert by_hour == [{"hour": 12, "mae": 200.0, "bias": 200.0, "count": 2}]
