import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.idempotency_record import IdempotencyRecord
from app.observability import metrics_store

IDEMPOTENCY_KEY_MAX_LENGTH = 255


@dataclass
class IdempotencyResult:
    replay: bool
    response_payload: dict[str, Any] | None = None


def validate_idempotency_key(idempotency_key: str | None) -> str | None:
    if idempotency_key is None:
        return None

    normalized_key = idempotency_key.strip()
    if not normalized_key:
        metrics_store.increment("idempotency_invalid_key_total")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key must not be empty",
        )

    if len(normalized_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
        metrics_store.increment("idempotency_invalid_key_total")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idempotency-Key exceeds max length {IDEMPOTENCY_KEY_MAX_LENGTH}",
        )

    return normalized_key


def _raise_payload_conflict() -> None:
    metrics_store.increment("idempotency_conflict_total")
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Idempotency key reused with different payload",
    )


def _hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _purge_expired_records(db: Session, now: datetime) -> int:
    result = db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.expires_at <= now))
    return int(result.rowcount or 0)


def check_idempotency(
    *,
    db: Session,
    user_id: str,
    route: str,
    idempotency_key: str,
    request_payload: Any,
) -> IdempotencyResult:
    now = datetime.now(timezone.utc)
    expired_count = _purge_expired_records(db, now)
    if expired_count:
        db.commit()
        metrics_store.increment("idempotency_purged_total", expired_count)

    payload_hash = _hash_payload(request_payload)
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.route == route,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )

    if not record:
        return IdempotencyResult(replay=False)

    if record.request_hash != payload_hash:
        _raise_payload_conflict()

    metrics_store.increment("idempotency_replay_total")
    return IdempotencyResult(replay=True, response_payload=record.response_payload)


def build_scope(route: str, *, user_id: str, order_id: str | None = None) -> str:
    if order_id:
        return f"{route}:user={user_id}:order={order_id}"
    return f"{route}:user={user_id}"


def save_idempotency_result(
    *,
    db: Session,
    user_id: str,
    route: str,
    idempotency_key: str,
    request_payload: Any,
    response_payload: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc)
    expired_count = _purge_expired_records(db, now)

    payload_hash = _hash_payload(request_payload)
    expires_at = now + timedelta(seconds=settings.idempotency_ttl_s)

    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.route == route,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    )
    if record is None:
        db.add(
            IdempotencyRecord(
                user_id=user_id,
                route=route,
                idempotency_key=idempotency_key,
                request_hash=payload_hash,
                response_payload=response_payload,
                expires_at=expires_at,
            )
        )
    else:
        if record.request_hash != payload_hash:
            _raise_payload_conflict()
        record.response_payload = response_payload
        record.expires_at = expires_at

    try:
        db.commit()
        if expired_count:
            metrics_store.increment("idempotency_purged_total", expired_count)
        metrics_store.increment("idempotency_store_total")
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.route == route,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise

        if existing.request_hash != payload_hash:
            _raise_payload_conflict()

        existing.response_payload = response_payload
        existing.expires_at = expires_at
        if expired_count:
            _purge_expired_records(db, now)
        db.commit()
        if expired_count:
            metrics_store.increment("idempotency_purged_total", expired_count)
        metrics_store.increment("idempotency_store_total")
