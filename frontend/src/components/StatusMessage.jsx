/** Shared loading / error placeholder. */
export default function StatusMessage({ loading, error }) {
  if (error) return <div className="status error">⚠ {error}</div>;
  if (loading) return <div className="status">Loading data from Elexon…</div>;
  return null;
}
