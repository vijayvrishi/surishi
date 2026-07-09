import { useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { useAuth, ROLE_LABELS } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export default function Profile() {
  const { user, isAdmin, isUserManager } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      toast.success("Password updated");
      setCurrent("");
      setNext("");
    } catch (e2) {
      toast.error(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <h1>Profile</h1>
      <div className="card card-pad" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 17, fontWeight: 800, color: "var(--ink-900)" }}>{user?.name}</div>
        <div style={{ fontSize: 13.5, color: "var(--ink-500)" }}>{user?.email}</div>
        <div style={{ marginTop: 8 }}>
          <span className="badge badge-brand">{ROLE_LABELS[user?.role] || user?.role}</span>
          {user?.hq && <span className="badge" style={{ background: "var(--ink-100)", color: "var(--ink-700)", marginLeft: 6 }}>{user.hq}</span>}
        </div>
      </div>

      {isAdmin && (
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          <h3>Admin Shortcuts</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Link className="btn btn-outline btn-sm" to="/tasks?upload=1">Upload Task Sheet</Link>
            <Link className="btn btn-outline btn-sm" to="/performance">Upload Performance Sheet</Link>
            {isUserManager && <Link className="btn btn-outline btn-sm" to="/users">Manage Users</Link>}
          </div>
        </div>
      )}

      <div className="card card-pad">
        <h3>Change Password</h3>
        <form onSubmit={submit}>
          <div className="field">
            <label className="field-label">Current Password</label>
            <input className="input" type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">New Password (min 6 chars)</label>
            <input className="input" type="password" required minLength={6} value={next} onChange={(e) => setNext(e.target.value)} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Updating…" : "Update Password"}
          </button>
        </form>
      </div>
    </div>
  );
}
