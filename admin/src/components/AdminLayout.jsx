import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Auth } from "../api.js";
import ThemeToggle from "./ThemeToggle.jsx";

const NAV = [
  { to: "/publishers", label: "ناشران" },
  { to: "/users", label: "کاربران" },
  { to: "/roles", label: "نقش‌ها" },
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
          <p className="brand">پژواک</p>
          <p className="muted small">پنل مدیریت</p>
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
          <p className="muted small">وارد شده به‌عنوان</p>
          <p className="sidebar-user">{user.username}</p>
          <div className="sidebar-actions">
            <ThemeToggle />
            <button type="button" className="ghost" onClick={logout}>
              خروج
            </button>
          </div>
        </div>
      </aside>

      <div className="admin-main">
        <Outlet />
      </div>
    </div>
  );
}
