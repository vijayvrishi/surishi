import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Tasks from "./pages/Tasks";
import TaskDetail from "./pages/TaskDetail";
import Reports from "./pages/Reports";
import Performance from "./pages/Performance";
import Profile from "./pages/Profile";
import Users from "./pages/Users";
import { Loader } from "./components/UI";

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-page"><Loader /></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function UserManagerRoute({ children }) {
  const { isUserManager, loading } = useAuth();
  if (loading) return <div className="center-page"><Loader /></div>;
  if (!isUserManager) return <Navigate to={firstAllowedPath()} replace />;
  return children;
}

const FEATURE_PATHS = [
  ["dashboard", "/"],
  ["tasks", "/tasks"],
  ["performance", "/performance"],
  ["reports", "/reports"],
];

function firstAllowedPath(hasFeature) {
  if (!hasFeature) return "/profile";
  const hit = FEATURE_PATHS.find(([f]) => hasFeature(f));
  return hit ? hit[1] : "/profile";
}

function FeatureRoute({ feature, children }) {
  const { hasFeature, loading } = useAuth();
  if (loading) return <div className="center-page"><Loader /></div>;
  if (!hasFeature(feature)) return <Navigate to={firstAllowedPath(hasFeature)} replace />;
  return children;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-page"><Loader /></div>;
  if (user) return <Navigate to="/" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
      <Route
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route path="/" element={<FeatureRoute feature="dashboard"><Dashboard /></FeatureRoute>} />
        <Route path="/tasks" element={<FeatureRoute feature="tasks"><Tasks /></FeatureRoute>} />
        <Route path="/tasks/:id" element={<FeatureRoute feature="tasks"><TaskDetail /></FeatureRoute>} />
        <Route path="/reports" element={<FeatureRoute feature="reports"><Reports /></FeatureRoute>} />
        <Route path="/performance" element={<FeatureRoute feature="performance"><Performance /></FeatureRoute>} />
        <Route path="/profile" element={<Profile />} />
        <Route
          path="/users"
          element={
            <UserManagerRoute>
              <Users />
            </UserManagerRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
