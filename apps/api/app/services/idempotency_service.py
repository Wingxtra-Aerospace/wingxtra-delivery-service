import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from app.config import settings
from app.services.store import store


@dataclass
class IdempotencyResult:
    replay: bool
    response_payload: dict[str, Any] | None = None


def _hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _purge_expired_records(now_s: float) -> None:
    expired_keys = [
        key
        for key, value in store.idempotency_records.items()
        if float(value.get("expires_at", 0)) <= now_s
    ]
    for key in expired_keys:
        store.idempotency_records.pop(key, None)


def check_idempotency(
    *,
    user_id: str,
    route: str,
    idempotency_key: str,
    request_payload: Any,
) -> IdempotencyResult:
    now_s = time.time()
    _purge_expired_records(now_s)

    payload_hash = _hash_payload(request_payload)
    record_key = (user_id, route, idempotency_key)
    record = store.idempotency_records.get(record_key)

    if not record:
        return IdempotencyResult(replay=False)

    if record["request_hash"] != payload_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key reused with different payload",
        )

    return IdempotencyResult(replay=True, response_payload=record["response_payload"])


def build_scope(route: str, *, user_id: str, order_id: str | None = None) -> str:
    if order_id:
        return f"{route}:user={user_id}:order={order_id}"
    return f"{route}:user={user_id}"


def save_idempotency_result(
    *,
    user_id: str,
    route: str,
    idempotency_key: str,
    request_payload: Any,
    response_payload: dict[str, Any],
) -> None:
    now_s = time.time()
    _purge_expired_records(now_s)

    payload_hash = _hash_payload(request_payload)
    record_key = (user_id, route, idempotency_key)
    store.idempotency_records[record_key] = {
        "request_hash": payload_hash,
        "response_payload": response_payload,
        "expires_at": now_s + settings.idempotency_ttl_s,
    }
