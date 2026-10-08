import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { AuthGate } from "./components/AuthGate";
import { SessionBar } from "./components/SessionBar";
import { useIncidents, useMonitors } from "./lib/api";
import { useAuth } from "./lib/auth";
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
  const { canEdit, openGate, role } = useAuth();

  // Below 900px the sidebar collapses into a header with a burger menu.
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => setMenuOpen(false), [location.pathname]);

  return (
    <div className="app">
      <nav className={menuOpen ? "sidebar sidebar--open" : "sidebar"}>
        <Link to="/" className="sidebar__brand">
          <span className="sidebar__logo">D</span>
          Deploy Watch
        </Link>
        <button
          className="sidebar__burger"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((o) => !o)}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            {menuOpen ? (
              <path d="M4 4l12 12M16 4L4 16" />
            ) : (
              <path d="M3 5.5h14M3 10h14M3 14.5h14" />
            )}
          </svg>
        </button>
        <div className="sidebar__links">
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
        {canEdit ? (
          <NavLink
            to="/monitors/new"
            className={({ isActive }) =>
              isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
            }
          >
            <span>Add monitor</span>
          </NavLink>
        ) : (
          <button className="sidebar__link sidebar__link--button" onClick={openGate}>
            <span>Add monitor</span>
          </button>
        )}
        </div>
        <div className="sidebar__foot">
          refreshing every 30s
        </div>
      </nav>
      <main className="main">
        <div className={role === "sandbox" ? "topbar topbar--sandbox" : "topbar"}>
          {!onDashboard && (
            <button className="btn nav__back" onClick={goBack}>
              ← Back
            </button>
          )}
          <SessionBar />
        </div>
        <Outlet />
        <AuthGate />
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
