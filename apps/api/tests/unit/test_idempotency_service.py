from fastapi import HTTPException

from app.services.idempotency_service import check_idempotency, save_idempotency_result
from app.services.store import store


def test_idempotency_record_expires(monkeypatch):
    store.idempotency_records.clear()

    fake_now = 1000.0
    monkeypatch.setattr("app.services.idempotency_service.time.time", lambda: fake_now)

    save_idempotency_result(
        user_id="ops-1",
        route="POST:/api/v1/orders:user=ops-1",
        idempotency_key="idem-1",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    replay = check_idempotency(
        user_id="ops-1",
        route="POST:/api/v1/orders:user=ops-1",
        idempotency_key="idem-1",
        request_payload={"a": 1},
    )
    assert replay.replay is True

    monkeypatch.setattr("app.services.idempotency_service.time.time", lambda: fake_now + 86500)
    expired = check_idempotency(
        user_id="ops-1",
        route="POST:/api/v1/orders:user=ops-1",
        idempotency_key="idem-1",
        request_payload={"a": 1},
    )
    assert expired.replay is False


def test_idempotency_key_conflict_when_payload_differs_before_expiration(monkeypatch):
    store.idempotency_records.clear()
    monkeypatch.setattr("app.services.idempotency_service.time.time", lambda: 2000.0)

    save_idempotency_result(
        user_id="ops-2",
        route="POST:/api/v1/orders:user=ops-2",
        idempotency_key="idem-2",
        request_payload={"a": 1},
        response_payload={"ok": True},
    )

    try:
        check_idempotency(
            user_id="ops-2",
            route="POST:/api/v1/orders:user=ops-2",
            idempotency_key="idem-2",
            request_payload={"a": 2},
        )
        raise AssertionError("Expected HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 409
