import socket
from collections.abc import Callable
from typing import Literal
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.integrations.errors import IntegrationError
from app.integrations.fleet_api_client import FleetApiClientProtocol
from app.observability import log_event, metrics_store

ReadinessStatus = Literal["ok", "error"]


def safe_dependency_status(
    dependency_name: str,
    checker: Callable[[], ReadinessStatus],
) -> ReadinessStatus:
    metrics_store.increment("readiness_dependency_checked_total")
    try:
        status = checker()
    except Exception as exc:  # defensive: readiness must fail closed to degraded
        metrics_store.increment("readiness_dependency_error_total")
        log_event(
            "readiness_dependency_check_failed",
            order_id=f"{dependency_name}:{type(exc).__name__}",
        )
        return "error"

    if status == "ok":
        return "ok"

    metrics_store.increment("readiness_dependency_error_total")
    if status != "error":
        log_event(
            "readiness_dependency_status_invalid",
            order_id=f"{dependency_name}:{status}",
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


def redis_dependency_status(redis_url: str, timeout_s: float = 1.0) -> ReadinessStatus:
    parsed = urlparse(redis_url)
    if parsed.scheme != "redis":
        return "error"

    host = parsed.hostname
    if not host:
        return "error"

    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as conn:
            conn.sendall(b"*1\r\n$4\r\nPING\r\n")
            payload = conn.recv(16)
    except OSError:
        return "error"

    return "ok" if payload.startswith(b"+PONG") else "error"


def fleet_dependency_status(fleet_client: FleetApiClientProtocol) -> ReadinessStatus:
    try:
        fleet_client.get_latest_telemetry()
    except IntegrationError:
        return "error"
    return "ok"
