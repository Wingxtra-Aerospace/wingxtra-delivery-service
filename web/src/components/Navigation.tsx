import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthProvider";
import { UserBadge } from "./UserBadge";

const navItems = [
  { to: "/", label: "Home" },
  { to: "/orders", label: "Orders" },
  { to: "/jobs", label: "Jobs" },
  { to: "/tracking", label: "Tracking" },
  { to: "/ops-console", label: "Ops Console" }
];

export function Navigation() {
  const { isAuthenticated, logout } = useAuth();

  return (
    <header className="app-header">
      <h1>Wingxtra Delivery UI</h1>
      <UserBadge />
      <nav>
        <ul className="nav-list">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  isActive ? "nav-link nav-link-active" : "nav-link"
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
          <li>
            {isAuthenticated ? (
              <button type="button" onClick={logout} className="logout-button">
                Logout
              </button>
            ) : (
              <NavLink to="/login" className="nav-link">
                Login
              </NavLink>
            )}
          </li>
        </ul>
      </nav>
    </header>
  );
}
