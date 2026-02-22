from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import RateLimitStatus, rate_limit_public_tracking
from app.db.session import get_db
from app.routers.rate_limit_headers import (
    RATE_LIMIT_SUCCESS_HEADERS,
    RATE_LIMIT_THROTTLED_HEADERS,
    apply_rate_limit_headers,
)
from app.schemas.ui import TrackingViewResponse
from app.services.ui_service import get_pod, tracking_view

router = APIRouter(prefix="/api/v1/tracking", tags=["tracking"])


@router.get(
    "/{public_tracking_id}",
    response_model=TrackingViewResponse,
    response_model_exclude_none=True,
    summary="Tracking view",
    responses={
        200: {"headers": RATE_LIMIT_SUCCESS_HEADERS},
        429: {"description": "Rate limit exceeded", "headers": RATE_LIMIT_THROTTLED_HEADERS},
    },
)
def tracking_endpoint(
    public_tracking_id: str,
    response: Response,
    db: Session = Depends(get_db),
    rate_limit: RateLimitStatus = Depends(rate_limit_public_tracking),
) -> TrackingViewResponse:
    apply_rate_limit_headers(
        response,
        limit=rate_limit.limit,
        remaining=rate_limit.remaining,
        reset_at_s=rate_limit.reset_at_s,
    )

    order = tracking_view(db, public_tracking_id)
    order_id = order.get("id") or order["order_id"]
    pod = get_pod(db, order_id)

    payload: dict[str, object] = {
        "order_id": order_id,
        "public_tracking_id": order["public_tracking_id"],
        "status": order["status"],
        "milestones": order.get("milestones"),
    }

    if pod is not None:
        payload["pod_summary"] = {
            "method": pod.method.value,
            "photo_url": pod.photo_url,
            "created_at": pod.created_at,
        }

    return TrackingViewResponse(**payload)
