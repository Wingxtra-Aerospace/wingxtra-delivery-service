import { useAuth } from "../AuthProvider";

export function UserBadge() {
  const { claims, isAuthenticated } = useAuth();

  if (!isAuthenticated || !claims) {
    return <p className="user-meta">Not logged in</p>;
  }

  const tenant = claims.tenant_id || claims.tenant || claims.merchant_id || "n/a";
  const user = claims.sub || "unknown";
  const role = claims.role || "unknown";

  return (
    <p className="user-meta">
      User: <strong>{user}</strong> · Role: <strong>{role}</strong> · Tenant: <strong>{tenant}</strong>
    </p>
  );
}
