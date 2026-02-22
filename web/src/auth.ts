export type Role = "CUSTOMER" | "MERCHANT" | "OPS" | "ADMIN";

export type UserClaims = {
  sub?: string;
  role?: string;
  tenant?: string;
  tenant_id?: string;
  merchant_id?: string;
  exp?: number;
};

const TOKEN_KEY = "wingxtra_ui_jwt";

let inMemoryToken: string | null = null;

function decodeBase64Url(value: string): string {
  const padLength = (4 - (value.length % 4)) % 4;
  const padded = `${value}${"=".repeat(padLength)}`.replace(/-/g, "+").replace(/_/g, "/");
  return atob(padded);
}

export function decodeJwtClaims(token: string): UserClaims | null {
  const parts = token.split(".");
  if (parts.length < 2) {
    return null;
  }

  try {
    const payload = decodeBase64Url(parts[1]);
    const parsed = JSON.parse(payload) as UserClaims;
    return parsed;
  } catch {
    return null;
  }
}

function isExpired(claims: UserClaims | null): boolean {
  if (!claims?.exp) {
    return false;
  }
  return Date.now() >= claims.exp * 1000;
}

export function loadTokenFromSession(): string | null {
  if (inMemoryToken) {
    return inMemoryToken;
  }

  const token = sessionStorage.getItem(TOKEN_KEY);
  if (!token) {
    return null;
  }

  const claims = decodeJwtClaims(token);
  if (isExpired(claims)) {
    clearToken();
    return null;
  }

  inMemoryToken = token;
  return token;
}

export function setToken(token: string): void {
  inMemoryToken = token;
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  inMemoryToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
}

export function getToken(): string | null {
  return loadTokenFromSession();
}

export function getCurrentUserClaims(): UserClaims | null {
  const token = getToken();
  if (!token) {
    return null;
  }

  const claims = decodeJwtClaims(token);
  if (isExpired(claims)) {
    clearToken();
    return null;
  }

  return claims;
}
