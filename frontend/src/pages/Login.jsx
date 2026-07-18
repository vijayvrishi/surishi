import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, apiErrorMessage } from "../api/client";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [forgotMsg, setForgotMsg] = useState("");

  async function handleForgot(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const res = await api.post("/auth/forgot-password", { email });
      setForgotMsg(res.data.detail);
    } catch (e2) {
      setErr(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

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
        <img
          src="/icons/icon-192.png"
          alt="Surishi Pharmaceuticals"
          width={110}
          height={110}
          style={{ borderRadius: 24, boxShadow: "var(--shadow-md)", marginBottom: 14 }}
        />
        <div style={{ fontSize: 14, color: "var(--gold-100)", opacity: 0.9 }}>Marketing Execution Portal</div>
      </div>
      {forgotMode ? (
        <form onSubmit={handleForgot} className="card card-pad" style={{ width: 360, maxWidth: "90vw" }}>
          <h2>Forgot password</h2>
          {forgotMsg ? (
            <>
              <div style={{ background: "var(--success-bg)", color: "var(--success)", padding: "10px 12px", borderRadius: 8, fontSize: 13.5, marginBottom: 14 }}>
                {forgotMsg}
              </div>
              <button
                type="button"
                className="btn btn-primary"
                style={{ width: "100%" }}
                onClick={() => { setForgotMode(false); setForgotMsg(""); }}
              >
                Back to sign in
              </button>
            </>
          ) : (
            <>
              <p style={{ fontSize: 13, color: "var(--ink-500)", marginBottom: 14 }}>
                Enter your email and we'll notify your administrator to reset your password.
              </p>
              {err && (
                <div style={{ background: "var(--danger-bg)", color: "var(--danger)", padding: "8px 12px", borderRadius: 8, fontSize: 13, marginBottom: 12 }}>
                  {err}
                </div>
              )}
              <div className="field">
                <label className="field-label">Email</label>
                <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@surishi.com" />
              </div>
              <button className="btn btn-primary" type="submit" style={{ width: "100%" }} disabled={busy}>
                {busy ? "Submitting…" : "Request password reset"}
              </button>
              <div style={{ marginTop: 14, fontSize: 13, textAlign: "center" }}>
                <a href="#" onClick={(e) => { e.preventDefault(); setForgotMode(false); setErr(""); }}>Back to sign in</a>
              </div>
            </>
          )}
        </form>
      ) : (
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
        <div style={{ marginTop: 10, fontSize: 13, textAlign: "center" }}>
          <a href="#" onClick={(e) => { e.preventDefault(); setForgotMode(true); setErr(""); }}>Forgot password?</a>
        </div>
        <div style={{ marginTop: 10, fontSize: 13, textAlign: "center", color: "var(--ink-500)" }}>
          New here? <Link to="/register">Create an account</Link>
        </div>
      </form>
      )}
      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.6)" }}>
        Demo password for all seeded accounts: Surishi@123
      </div>
    </div>
  );
}
