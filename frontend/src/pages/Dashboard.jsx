import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Loader, StatCard, StatusBadge, Progress, EmptyState } from "../components/UI";

export default function Dashboard() {
  const { user, isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .get("/dashboard")
      .then((res) => setData(res.data))
      .catch((e) => setErr(apiErrorMessage(e)));
  }, []);

  if (err) return <EmptyState text={err} />;
  if (!data) return <Loader label="Loading dashboard…" />;

  const { kpis, sales, todays_tasks, recent_tasks } = data;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <div>
          <h1>Welcome, {user?.name?.split(" ")[0]}</h1>
          <div style={{ color: "var(--ink-500)", fontSize: 14 }}>Here's this month at a glance.</div>
        </div>
        {isAdmin && (
          <div style={{ display: "flex", gap: 8 }}>
            <Link to="/tasks?upload=1" className="btn btn-gold btn-sm">Upload Excel</Link>
            <Link to="/tasks?create=1" className="btn btn-primary btn-sm">+ New Task</Link>
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 14, marginBottom: 20 }}>
        <StatCard label="Total Tasks" value={kpis.total} />
        <StatCard label="Completed" value={kpis.completed} accent="var(--success)" />
        <StatCard label="In Progress" value={kpis.in_progress} accent="var(--warn)" />
        <StatCard label="Overdue" value={kpis.overdue} accent="var(--danger)" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16, marginBottom: 20 }} className="dashboard-grid">
        <div className="card card-pad">
          <h3>Sales Collection vs Target</h3>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--ink-500)", marginBottom: 8 }}>
            <span>₹{sales.collected_total.toLocaleString("en-IN")} collected</span>
            <span>Target ₹{sales.target_total.toLocaleString("en-IN")}</span>
          </div>
          <Progress pct={sales.achievement_pct} color="var(--gold-600)" />
          <div style={{ marginTop: 8, fontSize: 13, color: "var(--ink-500)" }}>
            {sales.achievement_pct}% achieved · {sales.count} sales items
          </div>
        </div>
        <div className="card card-pad">
          <h3>Completion Rate</h3>
          <div style={{ fontSize: 34, fontWeight: 800, color: "var(--brand-700)" }}>{kpis.completion_rate}%</div>
          <Progress pct={kpis.completion_rate} />
          <div style={{ marginTop: 8, fontSize: 13, color: "var(--ink-500)" }}>
            {kpis.completed} of {kpis.total} tasks completed this month
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }} className="dashboard-grid">
        <div className="card card-pad">
          <h3>Today's Focus</h3>
          {todays_tasks.length === 0 ? (
            <EmptyState text="Nothing due today." />
          ) : (
            <TaskMiniList tasks={todays_tasks} />
          )}
        </div>
        <div className="card card-pad">
          <h3>Recently Added</h3>
          {recent_tasks.length === 0 ? (
            <EmptyState text="No tasks yet." />
          ) : (
            <TaskMiniList tasks={recent_tasks} />
          )}
        </div>
      </div>
    </div>
  );
}

function TaskMiniList({ tasks }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {tasks.map((t) => (
        <Link
          key={t.id}
          to={`/tasks/${t.id}`}
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", borderRadius: 8, background: "var(--ink-100)", color: "var(--ink-900)" }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.title}</div>
            <div style={{ fontSize: 11.5, color: "var(--ink-500)" }}>{t.hq || "—"} · {t.due_date || "no due date"}</div>
          </div>
          <StatusBadge status={t.status} />
        </Link>
      ))}
    </div>
  );
}
