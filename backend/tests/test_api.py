"""API tests using a fake Elexon client, so they run offline and fast."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.routes import get_client
from app.core.models import ActualPoint, ForecastPoint
from app.main import app

UTC = timezone.utc
JAN_1 = datetime(2026, 1, 1, tzinfo=UTC)


class FakeElexonClient:
    """Generates a simple, predictable month of data.

    Actual wind is a constant 10,000 MW. Every 3 hours a forecast run is
    published covering the next 48 hours; its error grows with horizon
    (10 MW per hour ahead), mimicking real forecast behaviour.
    """

    def __init__(self):
        self.actuals = [ActualPoint(JAN_1 + timedelta(minutes=30 * i), 10_000)
                        for i in range(31 * 48)]
        self.forecasts = []
        publish = JAN_1 - timedelta(days=3)
        while publish < JAN_1 + timedelta(days=31):
            for h in range(1, 49):
                self.forecasts.append(ForecastPoint(
                    start_time=publish + timedelta(hours=h),
                    publish_time=publish,
                    generation_mw=10_000 + 10 * h,
                ))
            publish += timedelta(hours=3)

    def get_actuals(self, start, end):
        return self.actuals

    def get_forecasts(self, publish_from, publish_to):
        return self.forecasts


app.dependency_overrides[get_client] = FakeElexonClient
client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_analysis_returns_series_and_metrics():
    res = client.get("/api/analysis", params={"start": "2026-01-05", "end": "2026-01-06",
                                              "horizon": 24})
    assert res.status_code == 200
    body = res.json()
    assert len(body["series"]) == 48            # 2 days x 24 hourly points
    # Forecasts published every 3h, so with a 24h horizon the chosen run is
    # 24-26h old -> error between 240 and 260 MW, always positive.
    assert 240 <= body["summary"]["mae"] <= 260
    assert body["summary"]["bias"] > 0


def test_analysis_rejects_dates_outside_january():
    res = client.get("/api/analysis", params={"start": "2026-03-01", "end": "2026-03-02"})
    assert res.status_code == 400


def test_horizon_curve_error_increases_with_horizon():
    curve = client.get("/api/horizon-curve").json()
    maes = [p["mae"] for p in curve]
    assert maes == sorted(maes)
    assert curve[0]["horizon"] == 0 and curve[-1]["horizon"] == 48


def test_forecast_at_uses_latest_run_before_decision():
    res = client.get("/api/forecast-at",
                     params={"decision_time": "2026-01-15T10:00:00Z", "hours_ahead": 24})
    body = res.json()
    # Runs are published at 00, 03, 06, 09 ... UTC -> latest before 10:00 is 09:00
    assert body["forecast_published"].startswith("2026-01-15T09:00")
    assert len(body["points"]) == 24
    assert all(p["band"] > 0 for p in body["points"])
    assert body["points"][0]["actual"] == 10_000
