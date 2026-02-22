from __future__ import annotations

import math
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import resolved_rate_limit_backend, settings


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_after_s: int
    reset_at_s: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = {}

    def check(self, key: str, *, max_requests: int, window_s: int) -> RateLimitResult:
        now = time.time()
        history = [value for value in self._buckets.get(key, []) if value > now - window_s]

        if len(history) >= max_requests:
            oldest = min(history)
            return _build_result(
                allowed=False,
                remaining=0,
                now=now,
                reset_deadline_s=oldest + window_s,
            )

        history.append(now)
        self._buckets[key] = history
        return _build_result(
            allowed=True,
            remaining=max_requests - len(history),
            now=now,
            reset_deadline_s=history[0] + window_s,
        )

    def reset(self) -> None:
        self._buckets.clear()


class RedisProtocolError(RuntimeError):
    pass


class RateLimiterBackendUnavailable(RuntimeError):
    pass


class RedisClient:
    def __init__(self, redis_url: str) -> None:
        parsed = urlparse(redis_url)
        if parsed.scheme != "redis" or not parsed.hostname:
            raise ValueError("REDIS_URL must use redis:// scheme and include a host")

        self.host = parsed.hostname
        self.port = parsed.port or 6379
        self.db = int(parsed.path.removeprefix("/") or 0)
        self.password = parsed.password

    def execute(self, *parts: str) -> object:
        payload = _encode_command(*parts)
        timeout = settings.redis_rate_limit_timeout_s
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout) as conn:
                conn.settimeout(timeout)
                if self.password:
                    conn.sendall(_encode_command("AUTH", self.password))
                    _read_response(conn)
                if self.db:
                    conn.sendall(_encode_command("SELECT", str(self.db)))
                    _read_response(conn)

                conn.sendall(payload)
                return _read_response(conn)
        except (OSError, TimeoutError, RedisProtocolError) as err:
            raise RateLimiterBackendUnavailable("Redis rate limiter is unavailable") from err


class RedisRateLimiter:
    def __init__(self, redis_url: str) -> None:
        self._client = RedisClient(redis_url)

    def check(self, key: str, *, max_requests: int, window_s: int) -> RateLimitResult:
        now = time.time()
        window_id = math.floor(now / window_s)
        reset_deadline_s = (window_id + 1) * window_s
        bucket_key = f"rl:{key}:{window_id}"

        count = int(self._client.execute("INCR", bucket_key))
        if count == 1:
            self._client.execute("EXPIRE", bucket_key, str(max(window_s, 1)))

        allowed = count <= max_requests
        remaining = max(max_requests - count, 0)
        return _build_result(
            allowed=allowed,
            remaining=remaining,
            now=now,
            reset_deadline_s=reset_deadline_s,
        )

    def reset(self) -> None:
        return None


def _build_result(
    *,
    allowed: bool,
    remaining: int,
    now: float,
    reset_deadline_s: float,
) -> RateLimitResult:
    reset_after_s = max(1, math.ceil(reset_deadline_s - now))
    reset_at_s = max(math.ceil(reset_deadline_s), math.ceil(now))
    return RateLimitResult(
        allowed=allowed,
        remaining=remaining,
        reset_after_s=reset_after_s,
        reset_at_s=reset_at_s,
    )


def _encode_command(*parts: str) -> bytes:
    command = f"*{len(parts)}\r\n".encode()
    for part in parts:
        data = str(part).encode()
        command += f"${len(data)}\r\n".encode() + data + b"\r\n"
    return command


def _read_line(conn: socket.socket) -> bytes:
    chunks = bytearray()
    while True:
        byte = conn.recv(1)
        if not byte:
            raise RedisProtocolError("Redis connection closed")
        chunks.extend(byte)
        if chunks.endswith(b"\r\n"):
            return bytes(chunks[:-2])


def _read_response(conn: socket.socket) -> object:
    prefix = conn.recv(1)
    if not prefix:
        raise RedisProtocolError("Redis connection closed")

    if prefix == b"+":
        return _read_line(conn).decode()
    if prefix == b"-":
        message = _read_line(conn).decode()
        raise RedisProtocolError(message)
    if prefix == b":":
        return int(_read_line(conn))
    if prefix == b"$":
        size = int(_read_line(conn))
        if size == -1:
            return None
        data = b""
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                raise RedisProtocolError("Redis bulk response truncated")
            data += chunk
        if conn.recv(2) != b"\r\n":
            raise RedisProtocolError("Redis bulk response missing terminator")
        return data.decode()
    if prefix == b"*":
        length = int(_read_line(conn))
        if length == -1:
            return []
        return [_read_response(conn) for _ in range(length)]

    raise RedisProtocolError("Unsupported Redis response type")


_memory_rate_limiter = InMemoryRateLimiter()
_redis_rate_limiter: RedisRateLimiter | None = None


class DisabledRateLimiter:
    def check(self, key: str, *, max_requests: int, window_s: int) -> RateLimitResult:  # noqa: ARG002
        now = time.time()
        return _build_result(
            allowed=True,
            remaining=max_requests,
            now=now,
            reset_deadline_s=now + max(window_s, 1),
        )

    def reset(self) -> None:
        return None


_disabled_rate_limiter = DisabledRateLimiter()


def _get_redis_rate_limiter() -> RedisRateLimiter:
    global _redis_rate_limiter
    if _redis_rate_limiter is None:
        _redis_rate_limiter = RedisRateLimiter(settings.redis_url)
    return _redis_rate_limiter


def get_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    backend = resolved_rate_limit_backend()
    if backend == "redis":
        return _get_redis_rate_limiter()
    if backend == "off":
        return _disabled_rate_limiter
    return _memory_rate_limiter


def reset_rate_limiter_state() -> None:
    global _redis_rate_limiter
    _memory_rate_limiter.reset()
    _redis_rate_limiter = None
