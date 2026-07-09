import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Loader, StatusBadge, HeadBadge, EmptyState, Modal } from "../components/UI";

const FREQUENCIES = ["daily", "weekly"];
const STATUSES = ["pending", "in_progress", "completed"];
const CATEGORIES = ["task", "sales_collection", "target"];
const HEADS = ["company", "scientific_inputs", "engagement"];
const HEAD_LABELS = { company: "Company", scientific_inputs: "Scientific Inputs", engagement: "Engagement" };
const CATEGORY_LABELS = { task: "Task", sales_collection: "Sales Collection", target: "Target" };

export default function Tasks() {
  const { isAdmin } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [tasks, setTasks] = useState(null);
  const [meta, setMeta] = useState({ hqs: [], assignees: [], roles: [] });
  const [filters, setFilters] = useState({
    frequency: "", status: "", hq: "", category: "", head: "", period: "", search: "",
  });
  const [showCreate, setShowCreate] = useState(params.get("create") === "1");
  const [showUpload, setShowUpload] = useState(params.get("upload") === "1");

  useEffect(() => {
    api.get("/meta/filters").then((res) => setMeta(res.data)).catch(() => {});
  }, []);

  const load = () => {
    const query = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
    api
      .get("/tasks", { params: query })
      .then((res) => setTasks(res.data))
      .catch((e) => toast.error(apiErrorMessage(e)));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  function setFilter(key, val) {
    setFilters((f) => ({ ...f, [key]: f[key] === val ? "" : val }));
  }

  function closeModals() {
    setShowCreate(false);
    setShowUpload(false);
    params.delete("create");
    params.delete("upload");
    setParams(params, { replace: true });
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ margin: 0 }}>Tasks</h1>
        {isAdmin && (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-gold btn-sm" onClick={() => setShowUpload(true)}>Upload Excel</button>
            <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>+ New Task</button>
          </div>
        )}
      </div>

      <div className="card card-pad" style={{ marginBottom: 16 }}>
        <input
          className="input"
          placeholder="Search tasks…"
          value={filters.search}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          style={{ marginBottom: 12 }}
        />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
          {["", "week", "month", "quarter"].map((p) => (
            <button key={p || "all"} className={`chip ${filters.period === p ? "active" : ""}`} onClick={() => setFilter("period", p)}>
              {p ? p[0].toUpperCase() + p.slice(1) : "All time"}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
          {FREQUENCIES.map((f) => (
            <button key={f} className={`chip ${filters.frequency === f ? "active" : ""}`} onClick={() => setFilter("frequency", f)}>
              {f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
          {STATUSES.map((s) => (
            <button key={s} className={`chip ${filters.status === s ? "active" : ""}`} onClick={() => setFilter("status", s)}>
              {s.replace("_", " ")}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
          {CATEGORIES.map((c) => (
            <button key={c} className={`chip ${filters.category === c ? "active" : ""}`} onClick={() => setFilter("category", c)}>
              {CATEGORY_LABELS[c]}
            </button>
          ))}
          {HEADS.map((h) => (
            <button key={h} className={`chip ${filters.head === h ? "active" : ""}`} onClick={() => setFilter("head", h)}>
              {HEAD_LABELS[h]}
            </button>
          ))}
        </div>
        {meta.hqs.length > 0 && (
          <select className="select" style={{ maxWidth: 220 }} value={filters.hq} onChange={(e) => setFilters((f) => ({ ...f, hq: e.target.value }))}>
            <option value="">All HQs</option>
            {meta.hqs.map((h) => <option key={h} value={h}>{h}</option>)}
          </select>
        )}
      </div>

      {tasks === null ? (
        <Loader />
      ) : tasks.length === 0 ? (
        <EmptyState text="No tasks match these filters." />
      ) : (
        <div className="card scroll-x">
          <table className="data-table">
            <thead>
              <tr>
                <th>Task</th><th>HQ</th><th>Assignee</th><th>Freq</th><th>Category</th><th>Head</th><th>Due</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id}>
                  <td style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis" }}>{t.title}</td>
                  <td>{t.hq || "—"}</td>
                  <td>{t.assignee || "—"}</td>
                  <td>{t.frequency}</td>
                  <td>{CATEGORY_LABELS[t.category] || t.category}</td>
                  <td><HeadBadge head={t.head} /></td>
                  <td>{t.due_date || "—"}</td>
                  <td><StatusBadge status={t.status} /></td>
                  <td><Link className="btn btn-outline btn-sm" to={`/tasks/${t.id}`}>Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <CreateTaskModal
          onClose={() => { setShowCreate(false); closeModals(); }}
          onCreated={() => { setShowCreate(false); closeModals(); load(); toast.success("Task created"); }}
        />
      )}
      {showUpload && (
        <UploadModal
          endpoint="/tasks/upload"
          title="Upload Task Sheet"
          hint="Expected columns: Task Name, Description, Assignee, Role, HQ, Frequency, Start/Due Date, Category, Target Amount, Reporting Due Date."
          onClose={() => { setShowUpload(false); closeModals(); }}
          onDone={() => load()}
        />
      )}
    </div>
  );
}

function CreateTaskModal({ onClose, onCreated }) {
  const toast = useToast();
  const [form, setForm] = useState({
    title: "", description: "", assignee: "", role: "", hq: "",
    frequency: "weekly", category: "task", head: "",
    start_date: "", due_date: "", reporting_due_date: "", target_amount: "",
  });
  const [busy, setBusy] = useState(false);

  function set(key, val) { setForm((f) => ({ ...f, [key]: val })); }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form };
      payload.target_amount = payload.target_amount ? parseFloat(payload.target_amount) : null;
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      await api.post("/tasks", payload);
      onCreated();
    } catch (e2) {
      toast.error(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="New Task" onClose={onClose} width={560}>
      <form onSubmit={submit}>
        <div className="field">
          <label className="field-label">Title *</label>
          <input className="input" required value={form.title} onChange={(e) => set("title", e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label">Description</label>
          <textarea className="textarea" value={form.description} onChange={(e) => set("description", e.target.value)} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div className="field">
            <label className="field-label">Assignee</label>
            <input className="input" value={form.assignee} onChange={(e) => set("assignee", e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">Role</label>
            <input className="input" value={form.role} onChange={(e) => set("role", e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">HQ</label>
            <input className="input" value={form.hq} onChange={(e) => set("hq", e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">Frequency</label>
            <select className="select" value={form.frequency} onChange={(e) => set("frequency", e.target.value)}>
              {FREQUENCIES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <div className="field">
            <label className="field-label">Category</label>
            <select className="select" value={form.category} onChange={(e) => set("category", e.target.value)}>
              {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>)}
            </select>
          </div>
          <div className="field">
            <label className="field-label">Activity Head</label>
            <select className="select" value={form.head} onChange={(e) => set("head", e.target.value)}>
              <option value="">—</option>
              {HEADS.map((h) => <option key={h} value={h}>{HEAD_LABELS[h]}</option>)}
            </select>
          </div>
          <div className="field">
            <label className="field-label">Start Date</label>
            <input className="input" type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">Due Date</label>
            <input className="input" type="date" value={form.due_date} onChange={(e) => set("due_date", e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">Reporting Due Date</label>
            <input className="input" type="date" value={form.reporting_due_date} onChange={(e) => set("reporting_due_date", e.target.value)} />
          </div>
          {form.category !== "task" && (
            <div className="field">
              <label className="field-label">Target Amount</label>
              <input className="input" type="number" step="0.01" value={form.target_amount} onChange={(e) => set("target_amount", e.target.value)} />
            </div>
          )}
        </div>
        <button className="btn btn-primary" type="submit" style={{ width: "100%" }} disabled={busy}>
          {busy ? "Creating…" : "Create Task"}
        </button>
      </form>
    </Modal>
  );
}

export function UploadModal({ endpoint, title, hint, onClose, onDone }) {
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function submit(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.post(endpoint, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(res.data);
      onDone();
      toast.success("Upload complete");
    } catch (e2) {
      toast.error(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <p style={{ fontSize: 13, color: "var(--ink-500)", marginBottom: 14 }}>{hint}</p>
      <form onSubmit={submit}>
        <input className="input" type="file" accept=".xlsx,.xlsm" onChange={(e) => setFile(e.target.files?.[0] || null)} style={{ marginBottom: 14 }} />
        <button className="btn btn-gold" type="submit" disabled={!file || busy} style={{ width: "100%" }}>
          {busy ? "Uploading…" : "Upload"}
        </button>
      </form>
      {result && (
        <div style={{ marginTop: 16, fontSize: 13.5 }}>
          <div style={{ color: "var(--success)", fontWeight: 700 }}>
            {result.inserted_count != null ? `${result.inserted_count} rows inserted` : `${result.type} data: ${result.inserted_count} rows across ${result.months?.join(", ")}`}
          </div>
          {result.skipped?.length > 0 && (
            <div style={{ marginTop: 8, color: "var(--warn)" }}>
              {result.skipped.length} row(s) skipped:
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                {result.skipped.slice(0, 10).map((s, i) => <li key={i}>Row {s.row}: {s.reason}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
