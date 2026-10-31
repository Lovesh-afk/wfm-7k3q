import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchAnalysis, fetchHorizonCurve } from "../api/client.js";
import { formatDateTime, formatDay, formatMW } from "../format.js";
import { useApi } from "../useApi.js";
import MetricCard from "./MetricCard.jsx";
import StatusMessage from "./StatusMessage.jsx";

/**
 * Purpose 2 from the brief: "evaluate the accuracy of the renewable
 * generation forecasts quantitatively, so that they can make their decisions
 * considering the quantified error".
 */
export default function AccuracyView() {
  const [start, setStart] = useState("2026-01-01");
  const [end, setEnd] = useState("2026-01-31");
  const [horizon, setHorizon] = useState(24);        // value used for queries
  const [sliderValue, setSliderValue] = useState(24); // value while dragging

  const analysis = useApi(() => fetchAnalysis({ start, end, horizon }), [start, end, horizon]);
  const curve = useApi(() => fetchHorizonCurve({ start, end }), [start, end]);

  const s = analysis.data?.summary;

  return (
    <section>
      <div className="panel controls">
        <label>
          From
          <input type="date" min="2026-01-01" max="2026-01-31" value={start}
                 onChange={(e) => e.target.value && setStart(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" min="2026-01-01" max="2026-01-31" value={end}
                 onChange={(e) => e.target.value && setEnd(e.target.value)} />
        </label>
        <label className="slider">
          <span>Forecast horizon: <strong>{sliderValue} h</strong> ahead</span>
          <input type="range" min="0" max="48" step="1" value={sliderValue}
                 onChange={(e) => setSliderValue(Number(e.target.value))}
                 onMouseUp={() => setHorizon(sliderValue)}
                 onTouchEnd={() => setHorizon(sliderValue)}
                 onKeyUp={() => setHorizon(sliderValue)} />
          <span className="caption">Uses the latest forecast published at least this long before each hour.</span>
        </label>
      </div>

      <StatusMessage loading={analysis.loading && !analysis.data} error={analysis.error} />

      {s && s.count > 0 && (
        <>
          <div className="metric-grid">
            <MetricCard label="Mean absolute error (MAE)" value={formatMW(s.mae)}
                        hint={`Average miss · ${((s.mae / s.mean_actual) * 100).toFixed(0)}% of average output`} />
            <MetricCard label="Bias (forecast − actual)" value={formatMW(s.bias)}
                        hint={s.bias > 0 ? "Forecasts tend to be too HIGH" : "Forecasts tend to be too LOW"}
                        tone={Math.abs(s.bias) > s.mae * 0.5 ? "warn" : ""} />
            <MetricCard label="MAE after removing bias" value={formatMW(s.mae_bias_corrected)}
                        hint="How accurate it would be if the systematic offset were corrected" />
            <MetricCard label="P90 absolute error" value={formatMW(s.p90_abs_error)}
                        hint="90% of hours were within this — a sensible safety margin" />
            <MetricCard label="RMSE" value={formatMW(s.rmse)} hint="Penalises large misses" />
            <MetricCard label="Hours compared" value={s.count.toLocaleString()}
                        hint={`MAPE ${s.mape ?? "—"}% · worst miss ${formatMW(s.max_abs_error)}`} />
          </div>

          <div className="panel">
            <h2>Actual vs forecast ({horizon} h ahead)</h2>
            <ResponsiveContainer width="100%" height={340}>
              <LineChart data={analysis.data.series} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="time" tickFormatter={formatDay} minTickGap={40} />
                <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)} GW`} width={60} />
                <Tooltip labelFormatter={formatDateTime} formatter={(v, n) => [formatMW(v), n]} />
                <Legend />
                <Line dataKey="actual" name="Actual" stroke="#111827" strokeWidth={1.5} dot={false} />
                <Line dataKey="forecast" name="Forecast" stroke="#2563eb" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="two-col">
            <div className="panel">
              <h2>How error grows with horizon</h2>
              <p className="caption">The further ahead you buy, the less reliable the forecast.</p>
              <StatusMessage loading={curve.loading && !curve.data} error={curve.error} />
              {curve.data && (
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={curve.data} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="horizon" tickFormatter={(h) => `${h}h`} />
                    <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)} GW`} width={60} />
                    <Tooltip labelFormatter={(h) => `${h} h ahead`} formatter={(v, n) => [formatMW(v), n]} />
                    <Legend />
                    <ReferenceLine x={horizon - (horizon % 3)} stroke="#f59e0b" strokeDasharray="4 4" />
                    <Line dataKey="mae" name="MAE" stroke="#2563eb" strokeWidth={2} />
                    <Line dataKey="p90_abs_error" name="P90 error" stroke="#dc2626" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="panel">
              <h2>When do forecasts miss? (by hour of day, UTC)</h2>
              <p className="caption">Bars above zero = forecast too high on average.</p>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={analysis.data.by_hour} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="hour" tickFormatter={(h) => `${h}:00`} />
                  <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)} GW`} width={60} />
                  <Tooltip labelFormatter={(h) => `${h}:00 UTC`} formatter={(v, n) => [formatMW(v), n]} />
                  <Legend />
                  <ReferenceLine y={0} stroke="#6b7280" />
                  <Bar dataKey="bias" name="Bias" fill="#f59e0b" />
                  <Bar dataKey="mae" name="MAE" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
