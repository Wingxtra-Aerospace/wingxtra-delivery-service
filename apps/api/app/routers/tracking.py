from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import RateLimitStatus, rate_limit_public_tracking
from app.db.session import get_db
from app.schemas.ui import TrackingViewResponse
from app.services.ui_service import get_pod, tracking_view

router = APIRouter(prefix="/api/v1/tracking", tags=["tracking"])


@router.get(
    "/{public_tracking_id}",
    response_model=TrackingViewResponse,
    response_model_exclude_none=True,
    summary="Tracking view",
)
def tracking_endpoint(
    public_tracking_id: str,
    response: Response,
    db: Session = Depends(get_db),
    rate_limit: RateLimitStatus = Depends(rate_limit_public_tracking),
) -> TrackingViewResponse:
    response.headers["X-RateLimit-Limit"] = str(rate_limit.limit)
    response.headers["X-RateLimit-Remaining"] = str(rate_limit.remaining)
    response.headers["X-RateLimit-Reset"] = str(rate_limit.reset_at_s)

    order = tracking_view(db, public_tracking_id)
    order_id = order.get("id") or order["order_id"]
    pod = get_pod(db, order_id)

    payload: dict[str, object] = {
        "order_id": order_id,
        "public_tracking_id": order["public_tracking_id"],
        "status": order["status"],
    }

    if pod is not None:
        payload["pod_summary"] = {
            "method": pod.method.value,
            "photo_url": pod.photo_url,
            "created_at": pod.created_at,
        }

    return TrackingViewResponse(**payload)
