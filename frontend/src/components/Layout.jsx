import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth, ROLE_LABELS } from "../context/AuthContext";
import { useState } from "react";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "📊", end: true },
  { to: "/tasks", label: "Tasks", icon: "✅" },
  { to: "/performance", label: "Performance", icon: "📈" },
  { to: "/reports", label: "Reports", icon: "📄" },
  { to: "/profile", label: "Profile", icon: "👤" },
];

export default function Layout() {
  const { user, logout, isUserManager } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const items = isUserManager
    ? [...NAV_ITEMS, { to: "/users", label: "Users", icon: "🛡️" }]
    : NAV_ITEMS;

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside
        className="sidebar"
        style={{
          width: 220,
          background: "var(--brand-900)",
          color: "#fff",
          display: "flex",
          flexDirection: "column",
          position: "sticky",
          top: 0,
          height: "100vh",
          flexShrink: 0,
        }}
      >
        <div style={{ padding: "20px 18px 12px" }}>
          <div style={{ fontWeight: 800, fontSize: 17, color: "#fff", letterSpacing: -0.3 }}>
            Surishi
          </div>
          <div style={{ fontSize: 11.5, color: "var(--gold-100)", opacity: 0.85, marginTop: 2 }}>
            Marketing Execution
          </div>
        </div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 2, padding: "8px 10px", flex: 1 }}>
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMenuOpen(false)}
              style={({ isActive }) => ({
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                borderRadius: 8,
                color: isActive ? "#fff" : "rgba(255,255,255,0.75)",
                background: isActive ? "var(--brand-700)" : "transparent",
                fontSize: 14,
                fontWeight: isActive ? 700 : 500,
              })}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div style={{ padding: 14, borderTop: "1px solid rgba(255,255,255,0.12)" }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>{user?.name}</div>
          <div style={{ fontSize: 11.5, color: "var(--gold-100)", opacity: 0.85, marginBottom: 10 }}>
            {ROLE_LABELS[user?.role] || user?.role}
          </div>
          <button className="btn btn-outline btn-sm" style={{ width: "100%", background: "transparent", color: "#fff", borderColor: "rgba(255,255,255,0.3)" }} onClick={handleLogout}>
            Log out
          </button>
        </div>
      </aside>
      <main style={{ flex: 1, minWidth: 0, background: "var(--bg)" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", padding: "22px 24px 60px" }}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
