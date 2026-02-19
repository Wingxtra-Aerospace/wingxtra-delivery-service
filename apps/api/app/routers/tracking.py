from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.tracking import PublicTrackingResponse
from app.services.orders_service import get_order_by_tracking_id
from app.services.pod_service import get_latest_pod_for_order

router = APIRouter(prefix="/api/v1/tracking", tags=["tracking"])


@router.get("/{public_tracking_id}", response_model=PublicTrackingResponse)
def get_public_tracking(
    public_tracking_id: str,
    db: Session = Depends(get_db),
) -> PublicTrackingResponse:
    order = get_order_by_tracking_id(db, public_tracking_id)
    pod_summary = None
    if order.status.value == "DELIVERED":
        pod = get_latest_pod_for_order(db, order.id)
        if pod:
            pod_summary = {
                "method": pod.method,
                "photo_url": pod.photo_url,
                "created_at": pod.created_at,
            }

    return PublicTrackingResponse(
        order_id=order.id,
        public_tracking_id=order.public_tracking_id,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        pod_summary=pod_summary,
    )
