export function Loader({ label = "Loading…" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: 30, color: "var(--ink-500)" }}>
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function StatCard({ label, value, sub, accent }) {
  return (
    <div className="card card-pad" style={{ minWidth: 0 }}>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-500)", textTransform: "uppercase", letterSpacing: 0.4 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 800, color: accent || "var(--ink-900)", marginTop: 6 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12.5, color: "var(--ink-500)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export function StatusBadge({ status }) {
  const labels = { pending: "Pending", in_progress: "In Progress", completed: "Completed" };
  return <span className={`badge badge-${status}`}>{labels[status] || status}</span>;
}

export function HeadBadge({ head }) {
  if (!head) return null;
  const labels = { company: "Company", scientific_inputs: "Scientific Inputs", engagement: "Engagement" };
  return <span className="badge badge-brand">{labels[head] || head}</span>;
}

export function Modal({ title, onClose, children, width }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={width ? { maxWidth: width } : undefined} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="btn btn-outline btn-sm" onClick={onClose}>Close</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function EmptyState({ text }) {
  return <div className="empty-state">{text}</div>;
}

export function Progress({ pct, color }) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  return (
    <div style={{ background: "var(--ink-100)", borderRadius: 999, height: 8, overflow: "hidden" }}>
      <div style={{ width: `${clamped}%`, height: "100%", background: color || "var(--brand-700)", borderRadius: 999 }} />
    </div>
  );
}
