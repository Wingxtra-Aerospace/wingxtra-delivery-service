import pytest
from fastapi import HTTPException

from app.models.order import OrderStatus
from app.schemas.order import OrderCreate
from app.schemas.pod import ProofOfDeliveryCreate
from app.services.orders_service import create_order
from app.services.pod_service import create_proof_of_delivery


def _order_payload() -> OrderCreate:
    return OrderCreate(
        pickup_lat=1,
        pickup_lng=2,
        dropoff_lat=3,
        dropoff_lng=4,
        payload_weight_kg=1.0,
        payload_type="BOX",
    )


def test_create_pod_for_delivered_order(db_session):
    order = create_order(db_session, _order_payload())
    order.status = OrderStatus.DELIVERED
    db_session.commit()

    pod = create_proof_of_delivery(
        db_session,
        order.id,
        ProofOfDeliveryCreate(method="PHOTO", photo_url="https://cdn/pod.jpg"),
    )

    assert pod.order_id == order.id
    assert pod.photo_url == "https://cdn/pod.jpg"


def test_create_pod_requires_delivered_status(db_session):
    order = create_order(db_session, _order_payload())

    with pytest.raises(HTTPException) as exc:
        create_proof_of_delivery(
            db_session,
            order.id,
            ProofOfDeliveryCreate(method="OPERATOR_CONFIRM", confirmed_by="ops@wingxtra"),
        )

    assert exc.value.status_code == 409


def test_create_pod_otp_is_hmac_hashed(db_session):
    order = create_order(db_session, _order_payload())
    order.status = OrderStatus.DELIVERED
    db_session.commit()

    pod = create_proof_of_delivery(
        db_session,
        order.id,
        ProofOfDeliveryCreate(method="OTP", otp_code="123456"),
    )

    assert pod.otp_hash is not None
    assert pod.otp_hash != "123456"
    assert len(pod.otp_hash) == 64


def test_create_pod_same_otp_produces_stable_hash(db_session):
    order = create_order(db_session, _order_payload())
    order.status = OrderStatus.DELIVERED
    db_session.commit()

    first = create_proof_of_delivery(
        db_session,
        order.id,
        ProofOfDeliveryCreate(method="OTP", otp_code="same-code"),
    )
    second = create_proof_of_delivery(
        db_session,
        order.id,
        ProofOfDeliveryCreate(method="OTP", otp_code="same-code"),
    )

    assert first.otp_hash == second.otp_hash
