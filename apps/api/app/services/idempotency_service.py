import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.idempotency_record import IdempotencyRecord


@dataclass
class IdempotencyResult:
    replay: bool
    response_payload: dict[str, Any] | None = None


def _hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _purge_expired_records(db: Session, now: datetime) -> None:
    db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.expires_at <= now))


def check_idempotency(
    *,
    db: Session,
    user_id: str,
    route: str,
    idempotency_key: str,
    request_payload: Any,
) -> IdempotencyResult:
    now = datetime.now(timezone.utc)
    _purge_expired_records(db, now)

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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key reused with different payload",
        )

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
    _purge_expired_records(db, now)

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
        record = IdempotencyRecord(
            user_id=user_id,
            route=route,
            idempotency_key=idempotency_key,
            request_hash=payload_hash,
            response_payload=response_payload,
            expires_at=expires_at,
        )
        db.add(record)
    else:
        record.request_hash = payload_hash
        record.response_payload = response_payload
        record.expires_at = expires_at

    db.commit()
