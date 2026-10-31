/**
 * Small wrapper around fetch for our backend.
 * All URLs are relative (/api/...) so the same code works with the Vite
 * dev proxy, Docker (nginx proxy) and Vercel.
 */

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function getJson(path, params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}${path}${query ? `?${query}` : ""}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const fetchAnalysis = ({ start, end, horizon }) =>
  getJson("/api/analysis", { start, end, horizon });

export const fetchHorizonCurve = ({ start, end }) =>
  getJson("/api/horizon-curve", { start, end });

export const fetchForecastAt = ({ decisionTime, hoursAhead = 48 }) =>
  getJson("/api/forecast-at", { decision_time: decisionTime, hours_ahead: hoursAhead });
