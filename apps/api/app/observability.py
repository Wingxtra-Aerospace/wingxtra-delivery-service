import json
import logging
import time
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", _request_id_ctx.get()),
            "order_id": getattr(record, "order_id", None),
            "job_id": getattr(record, "job_id", None),
            "drone_id": getattr(record, "drone_id", None),
        }
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


@dataclass
class MetricsSnapshot:
    counters: dict[str, int]
    timings: dict[str, dict[str, float]]


class MetricsStore:
    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._timings: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, amount: int = 1) -> None:
        self._counters[name] += amount

    def observe(self, name: str, value_s: float) -> None:
        self._timings[name].append(value_s)

    def reset(self) -> None:
        self._counters.clear()
        self._timings.clear()

    def snapshot(self) -> MetricsSnapshot:
        timings: dict[str, dict[str, float]] = {}
        for key, values in self._timings.items():
            if not values:
                continue
            timings[key] = {
                "count": float(len(values)),
                "avg_s": sum(values) / len(values),
                "max_s": max(values),
            }
        return MetricsSnapshot(counters=dict(self._counters), timings=timings)


metrics_store = MetricsStore()


def set_request_id(request_id: str) -> None:
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def log_event(
    message: str,
    *,
    order_id: str | None = None,
    job_id: str | None = None,
    drone_id: str | None = None,
) -> None:
    logging.getLogger("wingxtra.delivery").info(
        message,
        extra={
            "request_id": get_request_id(),
            "order_id": order_id,
            "job_id": job_id,
            "drone_id": drone_id,
        },
    )


class observe_timing:
    def __init__(self, metric_name: str) -> None:
        self.metric_name = metric_name
        self._start = 0.0

    def __enter__(self) -> "observe_timing":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed = time.perf_counter() - self._start
        metrics_store.observe(self.metric_name, elapsed)
