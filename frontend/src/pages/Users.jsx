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

  function load() {
    api.get("/users").then((res) => setUsers(res.data)).catch((e) => toast.error(apiErrorMessage(e)));
  }
  useEffect(load, []);

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

  if (users === null) return <Loader />;

  return (
    <div>
      <h1>User Management</h1>
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

      {editUser && (
        <EditUserModal user={editUser} onClose={() => setEditUser(null)} onSaved={() => { setEditUser(null); load(); }} />
      )}
      {resetUser && (
        <ResetPasswordModal user={resetUser} onClose={() => setResetUser(null)} />
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
