from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request, status

from app.auth.jwt import decode_jwt, jwt_http_exception
from app.config import allowed_roles_list, settings

AllowedRole = str


@dataclass
class AuthContext:
    user_id: str
    role: AllowedRole
    source: str | None = None


def get_auth_context(
    authorization: str | None = Header(default=None),
    x_wingxtra_source: str | None = Header(default=None),
) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise jwt_http_exception("Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_jwt(token, settings.jwt_secret)
    except Exception as err:
        raise jwt_http_exception("Invalid JWT") from err

    role = payload.get("role")
    user_id = payload.get("sub")
    if role not in allowed_roles_list() or not isinstance(user_id, str):
        raise jwt_http_exception("Invalid JWT claims")

    source = payload.get("source")
    if source == "gcs":
        if x_wingxtra_source != settings.gcs_auth_source:
            raise jwt_http_exception("Invalid GCS source header")
        role = "OPS"

    return AuthContext(user_id=user_id, role=role, source=source)


def require_roles(*roles: str) -> Callable[[AuthContext], AuthContext]:
    def dependency(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return auth

    return dependency


_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


def rate_limit_public_tracking(request: Request) -> None:
    import time

    now = time.time()
    window = settings.public_tracking_rate_limit_window_s
    max_requests = settings.public_tracking_rate_limit_requests
    key = request.client.host if request.client else "unknown"
    history = _RATE_LIMIT_BUCKETS.get(key, [])
    history = [value for value in history if value > now - window]
    if len(history) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    history.append(now)
    _RATE_LIMIT_BUCKETS[key] = history


def reset_public_tracking_limits() -> None:
    _RATE_LIMIT_BUCKETS.clear()
