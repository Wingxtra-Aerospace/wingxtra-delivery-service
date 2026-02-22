"""Dispatch worker tasks."""

from __future__ import annotations

from workers.dispatch_worker.worker import (
    DispatchRunResult,
    DispatchWorkerSettings,
    load_settings,
    run_dispatch_with_retries,
)


def dispatch_tick(settings: DispatchWorkerSettings | None = None) -> DispatchRunResult:
    """Run a single dispatch tick.

    Useful for cron-style scheduling or future queue integrations.
    """
    resolved_settings = settings or load_settings()
    return run_dispatch_with_retries(resolved_settings)
