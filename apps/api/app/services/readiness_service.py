import socket
from collections.abc import Callable
from typing import Literal
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.observability import log_event

ReadinessStatus = Literal["ok", "error"]


def safe_dependency_status(
    dependency_name: str,
    checker: Callable[[], ReadinessStatus],
) -> ReadinessStatus:
    try:
        return checker()
    except Exception as exc:  # defensive: readiness must fail closed to degraded
        log_event(
            "readiness_dependency_check_failed",
            order_id=f"{dependency_name}:{type(exc).__name__}",
        )
        return "error"


def database_dependency_status(
    session_factory: Callable[[], Session],
) -> ReadinessStatus:
    try:
        with session_factory() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "error"
    return "ok"


def redis_dependency_status(redis_url: str) -> ReadinessStatus:
    parsed = urlparse(redis_url)
    if parsed.scheme != "redis":
        return "error"

    host = parsed.hostname
    if not host:
        return "error"

    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=1.0) as conn:
            conn.sendall(b"*1\r\n$4\r\nPING\r\n")
            payload = conn.recv(16)
    except OSError:
        return "error"

    return "ok" if payload.startswith(b"+PONG") else "error"
