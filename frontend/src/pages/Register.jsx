import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, ROLES, ROLE_LABELS } from "../context/AuthContext";
import { apiErrorMessage } from "../api/client";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "", hq: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await register({ ...form, hq: form.hq || null });
      navigate("/");
    } catch (e2) {
      setErr(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-page" style={{ background: "var(--brand-900)", padding: "40px 0", flexDirection: "column", gap: 20 }}>
      <img
        src="/icons/icon-192.png"
        alt="Surishi Pharmaceuticals"
        width={90}
        height={90}
        style={{ borderRadius: 20, boxShadow: "var(--shadow-md)" }}
      />
      <form onSubmit={handleSubmit} className="card card-pad" style={{ width: 400, maxWidth: "90vw" }}>
        <h2>Create account</h2>
        {err && (
          <div style={{ background: "var(--danger-bg)", color: "var(--danger)", padding: "8px 12px", borderRadius: 8, fontSize: 13, marginBottom: 12 }}>
            {err}
          </div>
        )}
        <div className="field">
          <label className="field-label">Full name</label>
          <input className="input" required value={form.name} onChange={(e) => set("name", e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label">Email</label>
          <input className="input" type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label">Password (min 6 chars)</label>
          <input className="input" type="password" required minLength={6} value={form.password} onChange={(e) => set("password", e.target.value)} />
        </div>
        <div className="field">
          <label className="field-label">Role</label>
          <select className="select" required value={form.role} onChange={(e) => set("role", e.target.value)}>
            <option value="" disabled>Select a role</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field-label">HQ (optional)</label>
          <input className="input" value={form.hq} onChange={(e) => set("hq", e.target.value)} placeholder="e.g. Mumbai" />
        </div>
        <button className="btn btn-primary" type="submit" style={{ width: "100%" }} disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
        <div style={{ marginTop: 14, fontSize: 13, textAlign: "center", color: "var(--ink-500)" }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </form>
    </div>
  );
}
