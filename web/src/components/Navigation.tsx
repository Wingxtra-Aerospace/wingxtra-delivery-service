import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Home" },
  { to: "/orders", label: "Orders" },
  { to: "/jobs", label: "Jobs" },
  { to: "/tracking", label: "Tracking" },
  { to: "/ops-console", label: "Ops Console" }
];

export function Navigation() {
  return (
    <header className="app-header">
      <h1>Wingxtra Delivery UI</h1>
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
        </ul>
      </nav>
    </header>
  );
}
