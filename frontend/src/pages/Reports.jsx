import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { api, apiErrorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import { Loader, Progress, EmptyState, Modal, StatusBadge } from "../components/UI";

const PERIODS = ["week", "month", "quarter"];
const STATUS_COLORS = { completed: "#16a34a", in_progress: "#d97706", pending: "#94a3b8" };
const HEAD_LABELS = { company: "Company", scientific_inputs: "Scientific Inputs", engagement: "Engagement", Unassigned: "Unassigned" };

export default function Reports() {
  const toast = useToast();
  const [period, setPeriod] = useState("month");
  const [data, setData] = useState(null);
  const [drill, setDrill] = useState(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    setData(null);
    api.get("/reports", { params: { period } }).then((res) => setData(res.data)).catch((e) => toast.error(apiErrorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  async function downloadPdf() {
    setDownloading(true);
    try {
      const res = await api.get("/reports/pdf", { params: { period }, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `surishi_${period}_report.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setDownloading(false);
    }
  }

  async function openDrill(dimension, name) {
    try {
      const params = { period };
      if (dimension !== "all") params[dimension] = name;
      const res = await api.get("/tasks", { params });
      setDrill({ label: name, tasks: res.data });
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ margin: 0 }}>Reports</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {PERIODS.map((p) => (
            <button key={p} className={`chip ${period === p ? "active" : ""}`} onClick={() => setPeriod(p)}>
              {p[0].toUpperCase() + p.slice(1)}
            </button>
          ))}
          <button className="btn btn-gold btn-sm" onClick={downloadPdf} disabled={downloading}>
            {downloading ? "Preparing…" : "PDF"}
          </button>
        </div>
      </div>

      {!data ? (
        <Loader label="Loading report…" />
      ) : (
        <>
          <div style={{ fontSize: 13, color: "var(--ink-500)", marginBottom: 16 }}>
            {data.range.start} to {data.range.end}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }} className="dashboard-grid">
            <div className="card card-pad">
              <h3>Status Breakdown</h3>
              <div style={{ height: 220 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={[
                        { name: "Completed", value: data.kpis.completed, key: "completed" },
                        { name: "In Progress", value: data.kpis.in_progress, key: "in_progress" },
                        { name: "Pending", value: data.kpis.pending, key: "pending" },
                      ]}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={2}
                      onClick={(entry) => openDrill(entry.key === "completed" ? "status" : "status", entry.key)}
                      style={{ cursor: "pointer" }}
                    >
                      {["completed", "in_progress", "pending"].map((k) => (
                        <Cell key={k} fill={STATUS_COLORS[k]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ textAlign: "center", fontSize: 13, color: "var(--ink-500)" }}>
                Click a slice to drill down · {data.kpis.overdue} overdue
              </div>
            </div>

            <div className="card card-pad">
              <h3>Sales Collection vs Target</h3>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--ink-500)", marginBottom: 8 }}>
                <span>₹{data.sales.collected_total.toLocaleString("en-IN")}</span>
                <span>of ₹{data.sales.target_total.toLocaleString("en-IN")}</span>
              </div>
              <Progress pct={data.sales.achievement_pct} color="var(--gold-600)" />
              <div style={{ marginTop: 10, fontSize: 28, fontWeight: 800, color: "var(--gold-700)" }}>
                {data.sales.achievement_pct}%
              </div>
              <div style={{ fontSize: 13, color: "var(--ink-500)" }}>{data.sales.count} sales items this {period}</div>
            </div>
          </div>

          <DrillTable title="By HQ" rows={data.by_hq} onOpen={(name) => openDrill("hq", name)} />
          <DrillTable title="By Assignee" rows={data.by_assignee} onOpen={(name) => openDrill("assignee", name)} />
          <DrillTable title="By Role" rows={data.by_role} onOpen={(name) => openDrill("role", name)} />
          <DrillTable
            title="By Activity Head"
            rows={data.by_head}
            labelMap={HEAD_LABELS}
            onOpen={(name) => openDrill("head", name === "Unassigned" ? "" : name)}
          />
        </>
      )}

      {drill && (
        <Modal title={`Tasks — ${drill.label}`} onClose={() => setDrill(null)} width={640}>
          {drill.tasks.length === 0 ? (
            <EmptyState text="No tasks found." />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: "60vh", overflowY: "auto" }}>
              {drill.tasks.map((t) => (
                <div key={t.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", background: "var(--ink-100)", borderRadius: 8 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13.5 }}>{t.title}</div>
                    <div style={{ fontSize: 11.5, color: "var(--ink-500)" }}>{t.hq || "—"} · {t.assignee || "—"} · {t.due_date || "no due date"}</div>
                  </div>
                  <StatusBadge status={t.status} />
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

function DrillTable({ title, rows, onOpen, labelMap }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="card card-pad" style={{ marginBottom: 16 }}>
      <h3>{title}</h3>
      <div className="scroll-x">
        <table className="data-table">
          <thead>
            <tr><th>Name</th><th>Total</th><th>Completed</th><th>In Progress</th><th>Pending</th><th>Overdue</th><th>Rate</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} onClick={() => onOpen(r.name)} style={{ cursor: "pointer" }}>
                <td>{(labelMap && labelMap[r.name]) || r.name}</td>
                <td>{r.total}</td>
                <td>{r.completed}</td>
                <td>{r.in_progress}</td>
                <td>{r.pending}</td>
                <td>{r.overdue}</td>
                <td>{r.completion_rate}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
