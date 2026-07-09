import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Loader, StatusBadge, HeadBadge, EmptyState } from "../components/UI";

const STATUSES = ["pending", "in_progress", "completed"];

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
          <Field label="Role" value={task.role} />
          <Field label="HQ" value={task.hq} />
          <Field label="Category" value={task.category} />
          <Field label="Start Date" value={task.start_date} />
          <Field label="Due Date" value={task.due_date} />
          <Field label="Reporting Due" value={task.reporting_due_date} />
          {isSales && <Field label="Target Amount" value={task.target_amount ? `₹${task.target_amount.toLocaleString("en-IN")}` : "—"} />}
        </div>
      </div>

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
