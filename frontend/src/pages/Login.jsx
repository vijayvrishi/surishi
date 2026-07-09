import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiErrorMessage } from "../api/client";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (e2) {
      setErr(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-page" style={{ background: "var(--brand-900)", flexDirection: "column", gap: 24 }}>
      <div style={{ textAlign: "center", color: "#fff" }}>
        <div style={{ fontSize: 28, fontWeight: 800 }}>Surishi Pharmaceuticals</div>
        <div style={{ fontSize: 14, color: "var(--gold-100)", opacity: 0.9 }}>Marketing Execution Portal</div>
      </div>
      <form onSubmit={handleSubmit} className="card card-pad" style={{ width: 360, maxWidth: "90vw" }}>
        <h2>Sign in</h2>
        {err && (
          <div style={{ background: "var(--danger-bg)", color: "var(--danger)", padding: "8px 12px", borderRadius: 8, fontSize: 13, marginBottom: 12 }}>
            {err}
          </div>
        )}
        <div className="field">
          <label className="field-label">Email</label>
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@surishi.com" />
        </div>
        <div className="field">
          <label className="field-label">Password</label>
          <input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </div>
        <button className="btn btn-primary" type="submit" style={{ width: "100%" }} disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <div style={{ marginTop: 14, fontSize: 13, textAlign: "center", color: "var(--ink-500)" }}>
          New here? <Link to="/register">Create an account</Link>
        </div>
      </form>
      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.6)" }}>
        Demo password for all seeded accounts: Surishi@123
      </div>
    </div>
  );
}
