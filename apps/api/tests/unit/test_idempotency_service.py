from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.models.idempotency_record import IdempotencyRecord
from app.observability import metrics_store
from app.services.idempotency_service import (
    check_idempotency,
    save_idempotency_result,
    validate_idempotency_key,
)


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


def test_check_idempotency_commits_purge_of_expired_records(db_session):
    save_idempotency_result(
        db=db_session,
        user_id="ops-3",
        route="POST:/api/v1/orders:user=ops-3",
        idempotency_key="idem-3",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    db_session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.user_id == "ops-3")
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    db_session.commit()

    check_idempotency(
        db=db_session,
        user_id="ops-3",
        route="POST:/api/v1/orders:user=ops-3",
        idempotency_key="idem-3",
        request_payload={"a": 1},
    )

    remaining = db_session.scalar(
        select(func.count())
        .select_from(IdempotencyRecord)
        .where(IdempotencyRecord.user_id == "ops-3")
    )
    assert remaining == 0


def test_save_idempotency_result_updates_existing_scope(db_session):
    route = "POST:/api/v1/orders:user=ops-4"
    save_idempotency_result(
        db=db_session,
        user_id="ops-4",
        route=route,
        idempotency_key="idem-4",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    saved_payload = save_idempotency_result(
        db=db_session,
        user_id="ops-4",
        route=route,
        idempotency_key="idem-4",
        request_payload={"a": 1},
        response_payload={"ok": "updated"},
    )

    rows = db_session.scalars(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == "ops-4",
            IdempotencyRecord.route == route,
            IdempotencyRecord.idempotency_key == "idem-4",
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].response_payload == {"ok": True}
    assert saved_payload == {"ok": True}


def test_save_idempotency_result_handles_duplicate_insert_with_stable_response(db_session, monkeypatch):
    route = "POST:/api/v1/orders:user=ops-race"
    save_idempotency_result(
        db=db_session,
        user_id="ops-race",
        route=route,
        idempotency_key="idem-race",
        request_payload={"a": 1},
        response_payload={"order_id": "ord-original"},
    )

    original_scalar = db_session.scalar
    scalar_calls = {"count": 0}

    def race_scalar(statement):
        scalar_calls["count"] += 1
        if scalar_calls["count"] == 1:
            return None
        return original_scalar(statement)

    monkeypatch.setattr(db_session, "scalar", race_scalar)

    result = save_idempotency_result(
        db=db_session,
        user_id="ops-race",
        route=route,
        idempotency_key="idem-race",
        request_payload={"a": 1},
        response_payload={"order_id": "ord-concurrent"},
    )

    record = db_session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == "ops-race",
            IdempotencyRecord.route == route,
            IdempotencyRecord.idempotency_key == "idem-race",
        )
    )

    assert result == {"order_id": "ord-original"}
    assert record is not None
    assert record.response_payload == {"order_id": "ord-original"}


def test_save_idempotency_result_rejects_payload_mismatch_for_existing_key(db_session):
    route = "POST:/api/v1/orders:user=ops-5"
    save_idempotency_result(
        db=db_session,
        user_id="ops-5",
        route=route,
        idempotency_key="idem-5",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    with pytest.raises(HTTPException) as exc_info:
        save_idempotency_result(
            db=db_session,
            user_id="ops-5",
            route=route,
            idempotency_key="idem-5",
            request_payload={"a": 2},
            response_payload={"ok": "updated"},
        )

    assert exc_info.value.status_code == 409


def test_idempotency_metrics_are_recorded(db_session):
    snapshot_before = metrics_store.snapshot().counters

    def counter(name: str) -> int:
        current_value = int(metrics_store.snapshot().counters.get(name, 0))
        initial_value = int(snapshot_before.get(name, 0))
        return current_value - initial_value

    with pytest.raises(HTTPException):
        validate_idempotency_key("   ")

    save_idempotency_result(
        db=db_session,
        user_id="ops-metrics",
        route="POST:/api/v1/orders:user=ops-metrics",
        idempotency_key="idem-metrics",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    replay = check_idempotency(
        db=db_session,
        user_id="ops-metrics",
        route="POST:/api/v1/orders:user=ops-metrics",
        idempotency_key="idem-metrics",
        request_payload={"a": 1},
    )
    assert replay.replay is True

    db_session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.user_id == "ops-metrics")
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    db_session.commit()

    check_idempotency(
        db=db_session,
        user_id="ops-metrics",
        route="POST:/api/v1/orders:user=ops-metrics",
        idempotency_key="idem-metrics",
        request_payload={"a": 1},
    )

    save_idempotency_result(
        db=db_session,
        user_id="ops-metrics",
        route="POST:/api/v1/orders:user=ops-metrics",
        idempotency_key="idem-metrics",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    with pytest.raises(HTTPException):
        check_idempotency(
            db=db_session,
            user_id="ops-metrics",
            route="POST:/api/v1/orders:user=ops-metrics",
            idempotency_key="idem-metrics",
            request_payload={"a": 2},
        )

    assert counter("idempotency_invalid_key_total") == 1
    assert counter("idempotency_store_total") == 2
    assert counter("idempotency_replay_total") == 1
    assert counter("idempotency_conflict_total") == 1
    assert counter("idempotency_purged_total") == 1
