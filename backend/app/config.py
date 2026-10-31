"""
Central configuration for the Wind Forecast Monitor backend.

Keeping every "magic value" in one place makes the rest of the code easier
to read and makes it obvious what can be tuned.
"""

from datetime import datetime, timedelta, timezone

# --- Elexon BMRS API --------------------------------------------------------
ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
ACTUALS_DATASET = "FUELHH"   # actual generation by fuel type, half-hourly
FORECAST_DATASET = "WINDFOR"  # national wind generation forecast, hourly
WIND_FUEL_TYPE = "WIND"
HTTP_TIMEOUT_SECONDS = 30

# --- Scope of the challenge -------------------------------------------------
# We only care about delivery (target) times in January 2026.
TARGET_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
TARGET_END = datetime(2026, 2, 1, tzinfo=timezone.utc)  # exclusive

# Forecasts for early-January targets are published a few days earlier, so we
# fetch forecasts from a little before the target window.
FORECAST_LOOKBACK = timedelta(days=4)

# --- Forecast horizon -------------------------------------------------------
# "Horizon" = how many hours before the delivery time the forecast must have
# been published. 24h is a sensible default for day-ahead purchasing.
DEFAULT_HORIZON_HOURS = 24
MIN_HORIZON_HOURS = 0
MAX_HORIZON_HOURS = 48

# How long cached Elexon responses stay fresh (historical data rarely changes).
CACHE_TTL_SECONDS = 6 * 60 * 60
