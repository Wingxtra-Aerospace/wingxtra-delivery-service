from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.models.idempotency_record import IdempotencyRecord
from app.services.idempotency_service import check_idempotency, save_idempotency_result


def test_idempotency_record_expires(db_session):
    save_idempotency_result(
        db=db_session,
        user_id="ops-1",
        route="POST:/api/v1/orders:user=ops-1",
        idempotency_key="idem-1",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    replay = check_idempotency(
        db=db_session,
        user_id="ops-1",
        route="POST:/api/v1/orders:user=ops-1",
        idempotency_key="idem-1",
        request_payload={"a": 1},
    )
    assert replay.replay is True

    db_session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.user_id == "ops-1")
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    db_session.commit()

    expired = check_idempotency(
        db=db_session,
        user_id="ops-1",
        route="POST:/api/v1/orders:user=ops-1",
        idempotency_key="idem-1",
        request_payload={"a": 1},
    )
    assert expired.replay is False


def test_idempotency_key_conflict_when_payload_differs_before_expiration(db_session):
    save_idempotency_result(
        db=db_session,
        user_id="ops-2",
        route="POST:/api/v1/orders:user=ops-2",
        idempotency_key="idem-2",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    with pytest.raises(HTTPException) as exc_info:
        check_idempotency(
            db=db_session,
            user_id="ops-2",
            route="POST:/api/v1/orders:user=ops-2",
            idempotency_key="idem-2",
            request_payload={"a": 2},
        )

    assert exc_info.value.status_code == 409
