/** Formatting helpers shared by the charts and cards. */

export const formatMW = (value) =>
  value === null || value === undefined ? "—" : `${Math.round(value).toLocaleString("en-GB")} MW`;

export const formatGW = (value) =>
  value === null || value === undefined ? "—" : `${(value / 1000).toFixed(1)} GW`;

// Charts show UTC times (the market runs on UTC/GMT in January).
export const formatDateTime = (iso) =>
  new Date(iso).toLocaleString("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
  });

export const formatDay = (iso) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });
