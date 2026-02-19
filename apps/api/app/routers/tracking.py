from fastapi import APIRouter, Depends

from app.auth.dependencies import rate_limit_public_tracking
from app.schemas.ui import TrackingPodSummary, TrackingViewResponse
from app.services.ui_service import get_pod, tracking_view

router = APIRouter(prefix="/api/v1/tracking", tags=["tracking"])


@router.get("/{public_tracking_id}", response_model=TrackingViewResponse, summary="Tracking view")
def tracking_endpoint(
    public_tracking_id: str,
    _rate_limit: None = Depends(rate_limit_public_tracking),
) -> TrackingViewResponse:
    order = tracking_view(public_tracking_id)
    pod = get_pod(order.id)
    pod_summary = None
    if order.status == "DELIVERED" and pod is not None:
        pod_summary = TrackingPodSummary(method=pod.method, photo_url=pod.photo_url)

    return TrackingViewResponse(
        order_id=order.id,
        public_tracking_id=order.public_tracking_id,
        status=order.status,
        pod_summary=pod_summary,
    )
