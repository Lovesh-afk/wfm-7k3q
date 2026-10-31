"""
Forecast accuracy metrics.

All functions take a list of ComparisonPoint (actual vs forecast pairs) and
return plain numbers/dicts so they can be sent straight to the frontend.

Metric cheat-sheet (all in MW unless noted):
  - MAE   : average size of the error, ignoring direction. Easy to explain.
  - RMSE  : like MAE but punishes big misses more. Useful for risk.
  - Bias  : average signed error. Positive = forecasts tend to be too high.
  - MAPE  : average % error. Can blow up when actual wind is very low, so we
            skip near-zero actuals.
  - P90   : 90% of hours had an absolute error at or below this value.
            Handy for sizing a safety margin when buying power.
"""

import math
from collections import defaultdict
from statistics import mean

from .models import ComparisonPoint

# Ignore hours with tiny actual output when computing MAPE, otherwise a
# 50 MW miss on a 10 MW hour shows up as a 500% error.
MAPE_MIN_ACTUAL_MW = 500


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    lower, upper = math.floor(k), math.ceil(k)
    if lower == upper:
        return sorted_values[int(k)]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (k - lower)


def summary_metrics(rows: list[ComparisonPoint]) -> dict:
    """Headline accuracy numbers for the selected period and horizon."""
    if not rows:
        return {"count": 0, "mae": None, "rmse": None, "bias": None,
                "mae_bias_corrected": None,
                "mape": None, "p90_abs_error": None, "max_abs_error": None}

    errors = [r.error_mw for r in rows]
    abs_errors = sorted(abs(e) for e in errors)

    mape_rows = [r for r in rows if r.actual_mw >= MAPE_MIN_ACTUAL_MW]
    mape = (
        mean(abs(r.error_mw) / r.actual_mw for r in mape_rows) * 100
        if mape_rows else None
    )

    bias = mean(errors)

    return {
        "count": len(rows),
        "mae": round(mean(abs_errors), 1),
        "rmse": round(math.sqrt(mean(e * e for e in errors)), 1),
        "bias": round(bias, 1),
        # What MAE would be if we simply subtracted the average bias. A big
        # gap vs. MAE means the forecast is systematically off (fixable),
        # not just noisy.
        "mae_bias_corrected": round(mean(abs(e - bias) for e in errors), 1),
        "mape": round(mape, 1) if mape is not None else None,
        "p90_abs_error": round(_percentile(abs_errors, 0.9), 1),
        "max_abs_error": round(abs_errors[-1], 1),
        "mean_actual": round(mean(r.actual_mw for r in rows), 1),
    }


def error_by_hour_of_day(rows: list[ComparisonPoint]) -> list[dict]:
    """
    MAE and bias for each hour of the day (UTC), to show *when* forecasts
    tend to go wrong (e.g. evening ramps).
    """
    buckets: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        buckets[r.start_time.hour].append(r.error_mw)

    return [
        {
            "hour": hour,
            "mae": round(mean(abs(e) for e in errs), 1),
            "bias": round(mean(errs), 1),
            "count": len(errs),
        }
        for hour, errs in sorted(buckets.items())
    ]


def error_distribution(rows: list[ComparisonPoint], bin_mw: int = 500) -> list[dict]:
    """Histogram of signed errors, so users can see the spread and skew."""
    counts: dict[int, int] = defaultdict(int)
    for r in rows:
        bin_start = math.floor(r.error_mw / bin_mw) * bin_mw
        counts[bin_start] += 1
    return [{"bin_start": b, "bin_end": b + bin_mw, "count": c}
            for b, c in sorted(counts.items())]
