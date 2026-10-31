import { useMemo, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchForecastAt } from "../api/client.js";
import { formatDateTime, formatGW, formatMW } from "../format.js";
import { useApi } from "../useApi.js";
import MetricCard from "./MetricCard.jsx";
import StatusMessage from "./StatusMessage.jsx";

/**
 * Purpose 1 from the brief: "clearly understand the latest renewable
 * generation forecasts available when they need to make decisions".
 *
 * The trader picks the moment they are making the purchase decision; we show
 * the most recent forecast that existed at that moment, plus an uncertainty
 * band based on how wrong forecasts at that horizon were historically.
 */
export default function DecisionView() {
  const [date, setDate] = useState("2026-01-15");
  const [hour, setHour] = useState(10);
  const [showActuals, setShowActuals] = useState(true);

  const decisionTime = `${date}T${String(hour).padStart(2, "0")}:00:00Z`;
  const { data, loading, error } = useApi(
    () => fetchForecastAt({ decisionTime, hoursAhead: 48 }),
    [decisionTime]
  );

  // Reshape for Recharts: the band is drawn as a [low, high] range area.
  const chartData = useMemo(
    () =>
      (data?.points || []).map((p) => ({
        time: p.time,
        forecast: p.forecast,
        actual: p.actual,
        range: [Math.max(0, p.forecast - p.band), p.forecast + p.band],
      })),
    [data]
  );

  const stats = useMemo(() => {
    const values = (data?.points || []).map((p) => p.forecast);
    if (!values.length) return null;
    return {
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      min: Math.min(...values),
      max: Math.max(...values),
    };
  }, [data]);

  const ageHours = data
    ? (new Date(data.decision_time) - new Date(data.forecast_published)) / 3.6e6
    : null;

  return (
    <section>
      <div className="panel controls">
        <label>
          Decision date
          <input type="date" min="2026-01-01" max="2026-01-31" value={date}
                 onChange={(e) => e.target.value && setDate(e.target.value)} />
        </label>
        <label>
          Decision time (UTC)
          <select value={hour} onChange={(e) => setHour(Number(e.target.value))}>
            {Array.from({ length: 24 }, (_, h) => (
              <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>
            ))}
          </select>
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={showActuals}
                 onChange={(e) => setShowActuals(e.target.checked)} />
          Show what actually happened (hindsight)
        </label>
      </div>

      <StatusMessage loading={loading} error={error} />

      {data && stats && (
        <>
          <div className="metric-grid">
            <MetricCard label="Latest forecast published"
                        value={formatDateTime(data.forecast_published)}
                        hint={`${ageHours.toFixed(1)} h before your decision`} />
            <MetricCard label="Avg forecast, next 48 h" value={formatGW(stats.avg)}
                        hint={`Range ${formatGW(stats.min)} – ${formatGW(stats.max)}`} />
            <MetricCard label="Typical uncertainty"
                        value={`± ${formatMW(data.points[Math.min(24, data.points.length - 1)].band)}`}
                        hint="P90 historical error at ~24 h ahead" tone="warn" />
          </div>

          <div className="panel">
            <h2>Forecast available at {formatDateTime(data.decision_time)}</h2>
            <p className="caption">
              Shaded band = forecast ± the error that 90% of past forecasts at the same horizon
              stayed within. Plan purchases assuming wind could fall to the bottom of the band.
            </p>
            <ResponsiveContainer width="100%" height={380}>
              <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="time" tickFormatter={formatDateTime} minTickGap={40} />
                <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)} GW`} width={60} />
                <Tooltip labelFormatter={formatDateTime}
                         formatter={(v, name) => Array.isArray(v)
                           ? [`${formatMW(v[0])} – ${formatMW(v[1])}`, name]
                           : [formatMW(v), name]} />
                <Legend />
                <Area dataKey="range" name="Uncertainty band (P90)" fill="#93c5fd"
                      stroke="none" fillOpacity={0.35} />
                <Line dataKey="forecast" name="Forecast" stroke="#2563eb" strokeWidth={2}
                      dot={false} />
                {showActuals && (
                  <Line dataKey="actual" name="Actual" stroke="#111827" strokeWidth={1.5}
                        dot={false} connectNulls />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  );
}
