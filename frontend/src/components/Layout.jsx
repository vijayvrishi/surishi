import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth, ROLE_LABELS } from "../context/AuthContext";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "📊", end: true },
  { to: "/tasks", label: "Tasks", icon: "✅" },
  { to: "/performance", label: "Performance", icon: "📈" },
  { to: "/reports", label: "Reports", icon: "📄" },
  { to: "/profile", label: "Profile", icon: "👤" },
];

const MOBILE_QUERY = "(max-width: 768px)";

export default function Layout() {
  const { user, logout, isUserManager } = useAuth();
  const navigate = useNavigate();
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(MOBILE_QUERY).matches);
  const [sidebarOpen, setSidebarOpen] = useState(() =>
    window.matchMedia(MOBILE_QUERY).matches
      ? false
      : localStorage.getItem("surishi_sidebar") !== "closed"
  );

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const onChange = (e) => {
      setIsMobile(e.matches);
      setSidebarOpen(e.matches ? false : localStorage.getItem("surishi_sidebar") !== "closed");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function toggleSidebar() {
    setSidebarOpen((open) => {
      if (!isMobile) localStorage.setItem("surishi_sidebar", open ? "closed" : "open");
      return !open;
    });
  }

  function closeIfMobile() {
    if (isMobile) setSidebarOpen(false);
  }

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const items = isUserManager
    ? [...NAV_ITEMS, { to: "/users", label: "Users", icon: "🛡️" }]
    : NAV_ITEMS;

  const sidebarStyle = isMobile
    ? {
        position: "fixed",
        top: 0,
        left: 0,
        zIndex: 100,
        width: 240,
        transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
        transition: "transform 0.2s ease",
        boxShadow: sidebarOpen ? "var(--shadow-md)" : "none",
      }
    : {
        position: "sticky",
        top: 0,
        width: sidebarOpen ? 220 : 0,
        transition: "width 0.2s ease",
      };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside
        className="sidebar"
        style={{
          ...sidebarStyle,
          overflow: "hidden",
          background: "var(--brand-900)",
          color: "#fff",
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          flexShrink: 0,
          whiteSpace: "nowrap",
        }}
      >
        <div style={{ padding: "16px 18px 12px", display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: 17, color: "#fff", letterSpacing: -0.3 }}>
              Surishi
            </div>
            <div style={{ fontSize: 11.5, color: "var(--gold-100)", opacity: 0.85, marginTop: 2 }}>
              Marketing Execution
            </div>
          </div>
          <button
            onClick={toggleSidebar}
            title="Hide sidebar"
            aria-label="Hide sidebar"
            style={{
              background: "rgba(255,255,255,0.12)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              width: 30,
              height: 30,
              fontSize: 14,
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            {isMobile ? "✕" : "◀"}
          </button>
        </div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 2, padding: "8px 10px", flex: 1, overflowY: "auto" }}>
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={closeIfMobile}
              style={({ isActive }) => ({
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "11px 12px",
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

      {isMobile && sidebarOpen && (
        <div
          onClick={toggleSidebar}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.5)", zIndex: 99 }}
        />
      )}

      {!sidebarOpen && (
        <button
          onClick={toggleSidebar}
          title="Show sidebar"
          aria-label="Show sidebar"
          style={{
            position: "fixed",
            top: 12,
            left: 12,
            zIndex: 50,
            background: "var(--brand-900)",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            width: 40,
            height: 40,
            fontSize: 18,
            cursor: "pointer",
            boxShadow: "var(--shadow-md)",
            lineHeight: 1,
          }}
        >
          ☰
        </button>
      )}

      <main style={{ flex: 1, minWidth: 0, background: "var(--bg)" }}>
        <div
          style={{
            maxWidth: 1180,
            margin: "0 auto",
            padding: isMobile
              ? "64px 14px 60px"
              : sidebarOpen
                ? "22px 24px 60px"
                : "22px 24px 60px 68px",
          }}
        >
          <Outlet />
        </div>
      </main>
    </div>
  );
}
