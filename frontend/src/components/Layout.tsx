import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

const LINKS = [
  { to: "/", label: "Overview", end: true },
  { to: "/incidents", label: "Incidents" },
  { to: "/detections", label: "Detections" },
  { to: "/events", label: "Events" },
  { to: "/simulator", label: "Simulator" },
];

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <img src="/shield.svg" alt="" width={22} height={22} />
          <span>AEGIS</span>
        </div>
        <nav>
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end}>{l.label}</NavLink>
          ))}
          {user?.role === "admin" && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <div className="sidebar-footer">
          <div>
            <div className="strong">{user?.username}</div>
            <div className="muted small">{user?.role}</div>
          </div>
          <button className="btn small" onClick={logout}>Log out</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
