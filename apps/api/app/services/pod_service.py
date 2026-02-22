import hmac
from hashlib import sha256
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.order import OrderStatus
from app.models.proof_of_delivery import ProofOfDelivery, ProofOfDeliveryMethod
from app.schemas.pod import ProofOfDeliveryCreate
from app.services.orders_service import get_order


def _otp_hmac_hash(otp_code: str) -> str:
    return hmac.new(
        settings.pod_otp_hmac_secret.encode(),
        otp_code.encode(),
        sha256,
    ).hexdigest()


def create_proof_of_delivery(
    db: Session,
    order_id: uuid.UUID,
    payload: ProofOfDeliveryCreate,
) -> ProofOfDelivery:
    order = get_order(db, order_id)
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proof of delivery can only be added for DELIVERED orders",
        )

    if payload.method == ProofOfDeliveryMethod.PHOTO and not payload.photo_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="photo_url is required")
    if payload.method == ProofOfDeliveryMethod.OTP and not payload.otp_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="otp_code is required")
    if payload.method == ProofOfDeliveryMethod.OPERATOR_CONFIRM and not payload.confirmed_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirmed_by is required",
        )

    pod = ProofOfDelivery(
        order_id=order.id,
        method=payload.method,
        photo_url=payload.photo_url,
        otp_hash=_otp_hmac_hash(payload.otp_code) if payload.otp_code else None,
        confirmed_by=payload.confirmed_by,
        metadata_json=payload.metadata,
        notes=payload.notes,
    )
    db.add(pod)
    db.commit()
    db.refresh(pod)
    return pod


def get_latest_pod_for_order(db: Session, order_id: uuid.UUID) -> ProofOfDelivery | None:
    return db.scalar(
        select(ProofOfDelivery)
        .where(ProofOfDelivery.order_id == order_id)
        .order_by(ProofOfDelivery.created_at.desc())
    )
