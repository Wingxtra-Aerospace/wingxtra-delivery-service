"""Dispatch worker for periodic auto-assignment runs."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DispatchWorkerSettings:
    api_base_url: str
    interval_s: int
    timeout_s: float
    max_assignments: int | None
    auth_token: str | None


@dataclass(frozen=True)
class DispatchRunResult:
    ok: bool
    assigned_count: int
    status_code: int | None = None
    error: str | None = None


def load_settings(env: dict[str, str] | None = None) -> DispatchWorkerSettings:
    source = env if env is not None else os.environ
    api_base_url = source.get("WINGXTRA_DISPATCH_WORKER_API_BASE_URL", "http://localhost:8000").strip()
    interval_s = int(source.get("WINGXTRA_DISPATCH_WORKER_INTERVAL_S", "10"))
    timeout_s = float(source.get("WINGXTRA_DISPATCH_WORKER_TIMEOUT_S", "5"))
    max_assignments_value = source.get("WINGXTRA_DISPATCH_WORKER_MAX_ASSIGNMENTS")
    auth_token = source.get("WINGXTRA_DISPATCH_WORKER_AUTH_TOKEN")

    if interval_s < 1:
        raise ValueError("WINGXTRA_DISPATCH_WORKER_INTERVAL_S must be >= 1")
    if timeout_s <= 0:
        raise ValueError("WINGXTRA_DISPATCH_WORKER_TIMEOUT_S must be > 0")

    max_assignments: int | None = None
    if max_assignments_value is not None and max_assignments_value.strip() != "":
        max_assignments = int(max_assignments_value)
        if max_assignments < 1:
            raise ValueError("WINGXTRA_DISPATCH_WORKER_MAX_ASSIGNMENTS must be >= 1")

    return DispatchWorkerSettings(
        api_base_url=api_base_url.rstrip("/"),
        interval_s=interval_s,
        timeout_s=timeout_s,
        max_assignments=max_assignments,
        auth_token=auth_token,
    )


def run_dispatch_once(
    settings: DispatchWorkerSettings,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> DispatchRunResult:
    payload: dict[str, int] = {}
    if settings.max_assignments is not None:
        payload["max_assignments"] = settings.max_assignments

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=f"{settings.api_base_url}/api/v1/dispatch/run",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **(
                {"Authorization": f"Bearer {settings.auth_token}"}
                if settings.auth_token
                else {}
            ),
        },
    )

    try:
        with opener(request, timeout=settings.timeout_s) as response:
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            assigned = int(body.get("assigned_count", 0))
            return DispatchRunResult(
                ok=True,
                assigned_count=assigned,
                status_code=getattr(response, "status", 200),
            )
    except urllib.error.HTTPError as exc:
        return DispatchRunResult(
            ok=False,
            assigned_count=0,
            status_code=exc.code,
            error=f"HTTPError: {exc.code}",
        )
    except urllib.error.URLError as exc:
        return DispatchRunResult(
            ok=False,
            assigned_count=0,
            error=f"URLError: {exc.reason}",
        )


def run_forever(settings: DispatchWorkerSettings) -> None:
    while True:
        run_dispatch_once(settings)
        time.sleep(settings.interval_s)


if __name__ == "__main__":
    run_forever(load_settings())
