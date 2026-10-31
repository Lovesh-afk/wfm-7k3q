/** A single headline number with a short plain-English explanation. */
export default function MetricCard({ label, value, hint, tone }) {
  return (
    <div className={`metric-card ${tone || ""}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {hint && <div className="metric-hint">{hint}</div>}
    </div>
  );
}
