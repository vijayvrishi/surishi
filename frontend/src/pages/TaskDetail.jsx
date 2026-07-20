import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Loader, StatusBadge, HeadBadge, EmptyState, Progress } from "../components/UI";

const STATUSES = ["pending", "in_progress", "completed"];
const STATUS_LABELS = { pending: "Pending", in_progress: "In Progress", completed: "Completed" };
const STATUS_COLORS = { completed: "#16a34a", in_progress: "#d97706", pending: "#94a3b8" };

export default function TaskDetail() {
  const { id } = useParams();
  const { isAdmin } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [task, setTask] = useState(null);
  const [err, setErr] = useState("");
  const [collectedInput, setCollectedInput] = useState("");
  const [viewerPhoto, setViewerPhoto] = useState(null);

  function load() {
    api.get(`/tasks/${id}`).then((res) => {
      setTask(res.data);
      setCollectedInput(res.data.collected_amount ?? "");
    }).catch((e) => setErr(apiErrorMessage(e)));
  }

  useEffect(load, [id]);

  async function updateStatus(status) {
    try {
      const res = await api.patch(`/tasks/${id}`, { status });
      setTask(res.data);
      toast.success("Status updated");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  async function updateUnit(unit, status) {
    try {
      const res = await api.patch(`/tasks/${id}/completion`, { unit, status });
      setTask(res.data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  async function saveCollected() {
    try {
      const res = await api.patch(`/tasks/${id}`, { collected_amount: parseFloat(collectedInput || "0") });
      setTask(res.data);
      toast.success("Collected amount saved");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this task? This cannot be undone.")) return;
    try {
      await api.delete(`/tasks/${id}`);
      toast.success("Task deleted");
      navigate("/tasks");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  async function handlePhotoFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 4_000_000) {
      toast.error("Photo is too large (max 4MB)");
      return;
    }
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        await api.post(`/tasks/${id}/photos`, { photo_base64: reader.result });
        toast.success("Photo added");
        load();
      } catch (err2) {
        toast.error(apiErrorMessage(err2));
      }
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  async function deletePhoto(photoId) {
    try {
      await api.delete(`/tasks/${id}/photos/${photoId}`);
      load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  if (err) return <EmptyState text={err} />;
  if (!task) return <Loader label="Loading task…" />;

  const isSales = task.category === "sales_collection" || task.category === "target";

  return (
    <div style={{ maxWidth: 720 }}>
      <button className="btn btn-outline btn-sm" onClick={() => navigate(-1)} style={{ marginBottom: 14 }}>← Back</button>

      <div className="card card-pad" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
          <div>
            <h1 style={{ marginBottom: 6 }}>{task.title}</h1>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <StatusBadge status={task.status} />
              <HeadBadge head={task.head} />
              <span className="badge" style={{ background: "var(--ink-100)", color: "var(--ink-700)" }}>{task.frequency}</span>
            </div>
          </div>
          {isAdmin && <button className="btn btn-danger btn-sm" onClick={handleDelete}>Delete</button>}
        </div>

        {task.description && <p style={{ marginTop: 14, color: "var(--ink-700)" }}>{task.description}</p>}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 16, fontSize: 13.5 }}>
          <Field label="Assignee" value={task.assignee} />
          <Field label="Activity Category" value={task.activity_category} />
          <Field label="Frequency" value={task.frequency_label || task.frequency} />
          <Field label="Role" value={task.role} />
          <Field label="HQ" value={task.hq} />
          <Field label="Start Date" value={task.start_date} />
          <Field label="Due Date" value={task.due_date} />
          <Field label="Reporting Due" value={task.reporting_due_date} />
          {isSales && <Field label="Target Amount" value={task.target_amount ? `₹${task.target_amount.toLocaleString("en-IN")}` : "—"} />}
        </div>
      </div>

      {task.units && task.units.length > 0 ? (
        <CompletionCard task={task} onUpdateUnit={updateUnit} />
      ) : (
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          <h3>Update Status</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {STATUSES.map((s) => (
              <button
                key={s}
                className={`chip ${task.status === s ? "active" : ""}`}
                onClick={() => updateStatus(s)}
              >
                {s.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
      )}

      {isSales && (
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          <h3>Collected Amount</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="input" type="number" step="0.01" value={collectedInput} onChange={(e) => setCollectedInput(e.target.value)} />
            <button className="btn btn-primary btn-sm" onClick={saveCollected}>Save</button>
          </div>
        </div>
      )}

      <div className="card card-pad">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Activity Photos ({task.photos?.length || 0}/10)</h3>
          <label className="btn btn-outline btn-sm" style={{ margin: 0 }}>
            + Add Photo
            <input type="file" accept="image/*" capture="environment" onChange={handlePhotoFile} style={{ display: "none" }} />
          </label>
        </div>
        {!task.photos || task.photos.length === 0 ? (
          <EmptyState text="No photos yet." />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(90px, 1fr))", gap: 10 }}>
            {task.photos.map((p) => (
              <div key={p.id} style={{ position: "relative" }}>
                <img
                  src={p.data}
                  alt={p.caption || "photo"}
                  onClick={() => setViewerPhoto(p)}
                  style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 8, cursor: "pointer", border: "1px solid var(--border)" }}
                />
                <button
                  onClick={() => deletePhoto(p.id)}
                  title="Delete photo"
                  style={{ position: "absolute", top: 4, right: 4, background: "rgba(15,23,42,0.7)", color: "#fff", border: "none", borderRadius: 6, width: 22, height: 22, fontSize: 12, cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {viewerPhoto && (
        <div className="modal-backdrop" onClick={() => setViewerPhoto(null)}>
          <img src={viewerPhoto.data} alt="" style={{ maxWidth: "90vw", maxHeight: "90vh", borderRadius: 8 }} />
        </div>
      )}
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <div style={{ color: "var(--ink-500)", fontSize: 11.5, textTransform: "uppercase", fontWeight: 600 }}>{label}</div>
      <div style={{ color: "var(--ink-900)", fontWeight: 600 }}>{value || "—"}</div>
    </div>
  );
}

function CompletionCard({ task, onUpdateUnit }) {
  const completions = task.completions || [];
  const counts = { completed: 0, in_progress: 0, pending: 0 };
  completions.forEach((c) => { counts[c.status] = (counts[c.status] || 0) + 1; });
  const total = completions.length;
  const done = counts.completed;
  const pct = task.completion_pct ?? (total ? Math.round((done / total) * 100) : 0);
  const chartData = [
    { name: "Completed", key: "completed", value: counts.completed },
    { name: "In Progress", key: "in_progress", value: counts.in_progress },
    { name: "Pending", key: "pending", value: counts.pending },
  ].filter((d) => d.value > 0);

  return (
    <div className="card card-pad" style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, flexWrap: "wrap", gap: 8 }}>
        <h3 style={{ margin: 0 }}>Completion by Assignee</h3>
        <span className={`badge badge-${task.status}`}>
          {done}/{total} completed{task.status === "completed" ? " · Done" : ""}
        </span>
      </div>
      <p style={{ fontSize: 13, color: "var(--ink-500)", marginBottom: 12 }}>
        This task is complete only when all {total} assignees mark it completed.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 16, alignItems: "center" }} className="completion-grid">
        <div style={{ height: 150, position: "relative" }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={65} paddingAngle={2}>
                {chartData.map((d) => <Cell key={d.key} fill={STATUS_COLORS[d.key]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: "var(--brand-700)" }}>{pct}%</div>
          </div>
        </div>
        <div>
          <Progress pct={pct} color="var(--success)" />
          <div style={{ display: "flex", gap: 14, marginTop: 10, fontSize: 12.5, flexWrap: "wrap" }}>
            {STATUSES.map((s) => (
              <span key={s} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: 3, background: STATUS_COLORS[s], display: "inline-block" }} />
                {STATUS_LABELS[s]}: <b>{counts[s] || 0}</b>
              </span>
            ))}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
        {completions.map((c) => (
          <div key={c.unit} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "8px 10px", background: "var(--ink-100)", borderRadius: 8, flexWrap: "wrap" }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 13.5 }}>{c.unit}</div>
              {c.updated_by && (
                <div style={{ fontSize: 11.5, color: "var(--ink-500)" }}>
                  {STATUS_LABELS[c.status]} · by {c.updated_by}
                </div>
              )}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {STATUSES.map((s) => (
                <button
                  key={s}
                  className={`chip ${c.status === s ? "active" : ""}`}
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  onClick={() => onUpdateUnit(c.unit, s)}
                >
                  {s === "in_progress" ? "In prog." : STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
