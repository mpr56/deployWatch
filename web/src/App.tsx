import {
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { useIncidents, useMonitors } from "./lib/api";
import { Dashboard } from "./routes/Dashboard";
import { Incidents } from "./routes/Incidents";
import { Reports } from "./routes/Reports";
import { StatusPages } from "./routes/StatusPages";
import { IncidentDetail } from "./routes/IncidentDetail";
import { MonitorDetail } from "./routes/MonitorDetail";
import { MonitorForm } from "./routes/MonitorForm";
import { StatusPage } from "./routes/StatusPage";

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const monitors = useMonitors();
  const incidents = useIncidents();
  const openIncidents = incidents.data?.filter((i) => i.resolved_at === null).length ?? 0;

  // key === "default" means this is the first page in the session, so there
  // is no history entry to go back to; fall back to the dashboard.
  const goBack = () =>
    location.key === "default" ? navigate("/") : navigate(-1);

  const count = monitors.data?.length;
  const down = monitors.data?.filter((m) => m.current_status === "down").length;
  const onDashboard = location.pathname === "/";

  return (
    <div className="app">
      <nav className="sidebar">
        <Link to="/" className="sidebar__brand">
          <span className="sidebar__logo">D</span>
          Deploy Watch
        </Link>
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
          }
        >
          <span>Monitors</span>
          {count != null && (
            <span
              className={
                down ? "sidebar__badge sidebar__badge--alert" : "sidebar__badge"
              }
            >
              {down ? `${down} down` : count}
            </span>
          )}
        </NavLink>
        <NavLink
          to="/incidents"
          className={({ isActive }) =>
            isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
          }
        >
          <span>Incidents</span>
          {openIncidents > 0 && (
            <span className="sidebar__badge sidebar__badge--alert">{openIncidents} open</span>
          )}
        </NavLink>
        <NavLink
          to="/status-pages"
          className={({ isActive }) =>
            isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
          }
        >
          <span>Status pages</span>
        </NavLink>
        <NavLink
          to="/reports"
          className={({ isActive }) =>
            isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
          }
        >
          <span>Reports</span>
        </NavLink>
        <NavLink
          to="/monitors/new"
          className={({ isActive }) =>
            isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
          }
        >
          <span>Add monitor</span>
        </NavLink>
        <div className="sidebar__foot">
          refreshing every 30s
        </div>
      </nav>
      <main className="main">
        {!onDashboard && (
          <div className="topbar">
            <button className="btn nav__back" onClick={goBack}>
              ← Back
            </button>
          </div>
        )}
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
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/status-pages" element={<StatusPages />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
      </Route>
    </Routes>
  );
}
