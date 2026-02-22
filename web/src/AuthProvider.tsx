import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { clearToken, getCurrentUserClaims, getToken, setToken, type Role, type UserClaims } from "./auth";

type AuthContextValue = {
  token: string | null;
  claims: UserClaims | null;
  isAuthenticated: boolean;
  loginWithToken: (token: string) => { ok: boolean; message?: string };
  logout: () => void;
  hasRole: (roles: Role[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [claims, setClaims] = useState<UserClaims | null>(() => getCurrentUserClaims());

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setClaims(null);
  }, []);

  useEffect(() => {
    const handleAuthRequired = () => logout();
    window.addEventListener("wingxtra-auth-required", handleAuthRequired);
    return () => window.removeEventListener("wingxtra-auth-required", handleAuthRequired);
  }, [logout]);

  const loginWithToken = useCallback((inputToken: string) => {
    const normalized = inputToken.trim();
    if (!normalized) {
      return { ok: false, message: "Token is required." };
    }

    setToken(normalized);
    const nextClaims = getCurrentUserClaims();
    if (!nextClaims) {
      clearToken();
      return { ok: false, message: "Invalid JWT format." };
    }

    setTokenState(normalized);
    setClaims(nextClaims);
    return { ok: true };
  }, []);

  const hasRole = useCallback(
    (roles: Role[]) => {
      const role = claims?.role;
      if (!role) {
        return false;
      }
      return roles.includes(role as Role);
    },
    [claims]
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      claims,
      isAuthenticated: Boolean(token && claims),
      loginWithToken,
      logout,
      hasRole
    }),
    [token, claims, loginWithToken, logout, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
