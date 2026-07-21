import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth, ROLES, ROLE_LABELS } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Loader, Modal, EmptyState } from "../components/UI";

export default function Users() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [users, setUsers] = useState(null);
  const [editUser, setEditUser] = useState(null);
  const [resetUser, setResetUser] = useState(null);
  const [resetRequests, setResetRequests] = useState([]);

  function load() {
    api.get("/users").then((res) => setUsers(res.data)).catch((e) => toast.error(apiErrorMessage(e)));
    api.get("/admin/reset-requests").then((res) => setResetRequests(res.data)).catch(() => {});
  }
  useEffect(load, []);

  async function dismissRequest(id) {
    try {
      await api.delete(`/admin/reset-requests/${id}`);
      load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  async function handleDelete(u) {
    if (!window.confirm(`Delete user ${u.name}? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/users/${u.id}`);
      toast.success("User deleted");
      load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  async function handleClearData() {
    if (!window.confirm("Delete ALL tasks and ALL uploaded performance sheets? Users are kept. This cannot be undone.")) return;
    if (!window.confirm("Are you absolutely sure? Every task and uploaded sheet will be permanently removed.")) return;
    try {
      const res = await api.delete("/admin/data");
      const perf = Object.values(res.data.performance_deleted || {}).reduce((a, b) => a + b, 0);
      toast.success(`Cleared ${res.data.tasks_deleted} tasks and ${perf} performance rows`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  if (users === null) return <Loader />;

  return (
    <div>
      <h1>Users &amp; Access</h1>

      <FeatureAccessCard />


      {resetRequests.length > 0 && (
        <div className="card card-pad" style={{ marginBottom: 16, borderLeft: "4px solid var(--gold-600)" }}>
          <h3>Password Reset Requests ({resetRequests.length})</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {resetRequests.map((r) => {
              const target = users?.find((u) => u.email === r.email);
              return (
                <div key={r.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "8px 10px", background: "var(--gold-100)", borderRadius: 8, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>{r.user_name || r.email}</div>
                    <div style={{ fontSize: 12, color: "var(--ink-500)" }}>
                      {r.email} · requested {new Date(r.requested_at).toLocaleString()}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {target && (
                      <button className="btn btn-gold btn-sm" onClick={() => setResetUser(target)}>Reset password</button>
                    )}
                    <button className="btn btn-outline btn-sm" onClick={() => dismissRequest(r.id)}>Dismiss</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="card scroll-x">
        <table className="data-table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>HQ</th><th></th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td>
                <td>{u.email}</td>
                <td>{ROLE_LABELS[u.role] || u.role}</td>
                <td>{u.hq || "—"}</td>
                <td>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="btn btn-outline btn-sm" onClick={() => setEditUser(u)}>Edit</button>
                    <button className="btn btn-outline btn-sm" onClick={() => setResetUser(u)}>Reset PW</button>
                    {u.id !== me.id && (
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(u)}>Delete</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card card-pad" style={{ marginTop: 20, borderLeft: "4px solid var(--danger)" }}>
        <h3 style={{ color: "var(--danger)" }}>Danger Zone</h3>
        <p style={{ fontSize: 13.5, color: "var(--ink-700)", marginBottom: 12 }}>
          Permanently delete <b>all tasks</b> and <b>all uploaded performance sheets</b>. User accounts are kept. This cannot be undone.
        </p>
        <button className="btn btn-danger" onClick={handleClearData}>Clear all tasks &amp; uploaded data</button>
      </div>

      {editUser && (
        <EditUserModal user={editUser} onClose={() => setEditUser(null)} onSaved={() => { setEditUser(null); load(); }} />
      )}
      {resetUser && (
        <ResetPasswordModal user={resetUser} onClose={() => { setResetUser(null); load(); }} />
      )}
    </div>
  );
}

function EditUserModal({ user, onClose, onSaved }) {
  const toast = useToast();
  const [role, setRole] = useState(user.role);
  const [hq, setHq] = useState(user.hq || "");
  const [name, setName] = useState(user.name);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch(`/admin/users/${user.id}`, { role, hq: hq || null, name });
      toast.success("User updated");
      onSaved();
    } catch (e2) {
      toast.error(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Edit ${user.name}`} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="field">
          <label className="field-label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label">Role</label>
          <select className="select" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field-label">HQ</label>
          <input className="input" value={hq} onChange={(e) => setHq(e.target.value)} />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Saving…" : "Save"}
        </button>
      </form>
    </Modal>
  );
}

function ResetPasswordModal({ user, onClose }) {
  const toast = useToast();
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/admin/users/${user.id}/reset-password`, { new_password: pw });
      toast.success(`Password reset for ${user.name}`);
      onClose();
    } catch (e2) {
      toast.error(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Reset password — ${user.name}`} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="field">
          <label className="field-label">New Password (min 6 chars)</label>
          <input className="input" type="password" required minLength={6} value={pw} onChange={(e) => setPw(e.target.value)} />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Resetting…" : "Reset Password"}
        </button>
      </form>
    </Modal>
  );
}

function FeatureAccessCard() {
  const toast = useToast();
  const { loadFeatures } = useAuth();
  const [data, setData] = useState(null);
  const [perms, setPerms] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/admin/permissions").then((res) => {
      setData(res.data);
      setPerms(res.data.permissions || {});
    }).catch((e) => toast.error(apiErrorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggle(role, feature) {
    setPerms((p) => {
      const cur = new Set(p[role] || []);
      cur.has(feature) ? cur.delete(feature) : cur.add(feature);
      return { ...p, [role]: [...cur] };
    });
  }

  async function save() {
    setBusy(true);
    try {
      await api.put("/admin/permissions", { permissions: perms });
      await loadFeatures(); // refresh own nav in case chairman changed something
      toast.success("Feature access saved");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (!data) return null;

  return (
    <div className="card card-pad" style={{ marginBottom: 16, borderLeft: "4px solid var(--brand-700)" }}>
      <h3>Feature Access</h3>
      <p style={{ fontSize: 13, color: "var(--ink-500)", marginBottom: 12 }}>
        Choose which features each role can see. Chairman always has full access; Profile is always visible.
      </p>
      <div className="scroll-x">
        <table className="data-table">
          <thead>
            <tr>
              <th>Role</th>
              {data.features.map((f) => <th key={f} style={{ textAlign: "center" }}>{data.labels[f]}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.roles.map((role) => (
              <tr key={role}>
                <td style={{ fontWeight: 600 }}>{data.role_labels[role]}</td>
                {data.features.map((f) => (
                  <td key={f} style={{ textAlign: "center" }}>
                    <input
                      type="checkbox"
                      style={{ width: 18, height: 18, cursor: "pointer" }}
                      checked={(perms[role] || []).includes(f)}
                      onChange={() => toggle(role, f)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={save} disabled={busy}>
        {busy ? "Saving…" : "Save Feature Access"}
      </button>
    </div>
  );
}
