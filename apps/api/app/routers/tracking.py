from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.tracking import PublicTrackingResponse
from app.services.orders_service import get_order_by_tracking_id

router = APIRouter(prefix="/api/v1/tracking", tags=["tracking"])


@router.get("/{public_tracking_id}", response_model=PublicTrackingResponse)
def get_public_tracking(
    public_tracking_id: str,
    db: Session = Depends(get_db),
) -> PublicTrackingResponse:
    order = get_order_by_tracking_id(db, public_tracking_id)
    return PublicTrackingResponse(
        order_id=order.id,
        public_tracking_id=order.public_tracking_id,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
