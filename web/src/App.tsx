import {
  Link,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { Dashboard } from "./routes/Dashboard";
import { IncidentDetail } from "./routes/IncidentDetail";
import { MonitorDetail } from "./routes/MonitorDetail";
import { MonitorForm } from "./routes/MonitorForm";
import { StatusPage } from "./routes/StatusPage";

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();

  // key === "default" means this is the first page in the session, so there
  // is no history entry to go back to; fall back to the dashboard.
  const goBack = () =>
    location.key === "default" ? navigate("/") : navigate(-1);

  return (
    <div className="app">
      <nav className="nav">
        {location.pathname !== "/" && (
          <button className="btn nav__back" onClick={goBack}>
            ← Back
          </button>
        )}
        <Link to="/" className="nav__brand">
          DeployWatch
        </Link>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      {/* The public status page lives outside the shell on purpose: no nav,
          no controls, no shared chrome. Different audience, different product. */}
      <Route path="/status/:slug" element={<StatusPage />} />

      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="/monitors/new" element={<MonitorForm />} />
        <Route path="/monitors/:id" element={<MonitorDetail />} />
        <Route path="/monitors/:id/edit" element={<MonitorForm />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
      </Route>
    </Routes>
  );
}
