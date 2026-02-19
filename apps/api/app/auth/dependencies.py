from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.config import settings


@dataclass
class AuthContext:
    source: str
    role: str


def require_gcs_ops_auth(
    authorization: str | None = Header(default=None),
    x_wingxtra_source: str | None = Header(default=None),
) -> AuthContext:
    expected_source = settings.gcs_auth_source
    expected_token = settings.gcs_auth_token

    if x_wingxtra_source != expected_source:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth source")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if token != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token")

    return AuthContext(source=expected_source, role="OPS")
