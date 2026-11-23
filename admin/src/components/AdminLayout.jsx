import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Auth } from "../api.js";

const NAV = [
  { to: "/publishers", label: "Publishers" },
  { to: "/users", label: "Users" },
  { to: "/roles", label: "Roles" },
];

export default function AdminLayout({ user, onLogout }) {
  const location = useLocation();

  async function logout() {
    await Auth.logout().catch(() => {});
    onLogout();
  }

  function linkActive(to, isActive) {
    if (to === "/publishers" && location.pathname.startsWith("/listen/")) {
      return true;
    }
    return isActive;
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <p className="brand">StreamAudio</p>
          <p className="muted small">Admin</p>
        </div>

        <nav className="sidebar-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `sidebar-link${linkActive(item.to, isActive) ? " active" : ""}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <p className="muted small">Signed in as</p>
          <p className="sidebar-user">{user.username}</p>
          <button type="button" className="ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>

      <div className="admin-main">
        <Outlet />
      </div>
    </div>
  );
}
