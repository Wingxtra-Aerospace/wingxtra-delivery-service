import { ReactElement } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../AuthProvider";
import { type Role } from "../auth";

export function ProtectedRoute({
  roles,
  children
}: {
  roles: Role[];
  children: ReactElement;
}) {
  const location = useLocation();
  const { isAuthenticated, hasRole } = useAuth();

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location.pathname,
          message: "Please login with an OPS/DEV JWT to access this route."
        }}
      />
    );
  }

  if (!hasRole(roles)) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location.pathname,
          message: `Unauthorized route. Required roles: ${roles.join(", ")}.`
        }}
      />
    );
  }

  return children;
}
