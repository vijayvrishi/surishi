import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "../api/client";

const AuthContext = createContext(null);

const ADMIN_ROLES = new Set(["marketing_head", "marketing_deputy_head", "chairman"]);
const USER_MANAGER_ROLES = new Set(["chairman"]);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("surishi_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("surishi_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((res) => {
        setUser(res.data);
        localStorage.setItem("surishi_user", JSON.stringify(res.data));
      })
      .catch(() => {
        localStorage.removeItem("surishi_token");
        localStorage.removeItem("surishi_user");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    localStorage.setItem("surishi_token", res.data.access_token);
    localStorage.setItem("surishi_user", JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  }, []);

  const register = useCallback(async (payload) => {
    const res = await api.post("/auth/register", payload);
    localStorage.setItem("surishi_token", res.data.access_token);
    localStorage.setItem("surishi_user", JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("surishi_token");
    localStorage.removeItem("surishi_user");
    setUser(null);
  }, []);

  const isAdmin = !!user && ADMIN_ROLES.has(user.role);
  const isUserManager = !!user && USER_MANAGER_ROLES.has(user.role);

  return (
    <AuthContext.Provider
      value={{ user, setUser, loading, login, register, logout, isAdmin, isUserManager }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export const ROLES = [
  "marketing_head",
  "marketing_deputy_head",
  "product_executive",
  "general_manager",
  "ceo",
  "chairman",
  "agm",
  "business_manager",
];

export const ROLE_LABELS = {
  marketing_head: "Marketing Head",
  marketing_deputy_head: "Marketing Deputy Head",
  product_executive: "Product Executive",
  general_manager: "General Manager",
  ceo: "CEO",
  chairman: "Chairman",
  agm: "AGM",
  business_manager: "Business Manager",
};
