from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import RateLimitStatus, rate_limit_public_tracking
from app.db.session import get_db
from app.routers.rate_limit_headers import (
    RATE_LIMIT_SUCCESS_HEADERS,
    RATE_LIMIT_THROTTLED_HEADERS,
    apply_rate_limit_headers,
)
from app.schemas.ui import TrackingViewResponse
from app.services.safety import assert_production_safe
from app.services.ui_service import (
    build_public_tracking_etag,
    build_public_tracking_payload,
    etag_matches,
)

router = APIRouter(prefix="/api/v1/tracking", tags=["tracking"])

ETAG_RESPONSE_HEADER = {
    "ETag": {
        "description": "Entity tag representing the current tracking payload",
        "schema": {"type": "string"},
    }
}


@router.get(
    "/{public_tracking_id}",
    response_model=TrackingViewResponse,
    response_model_exclude_none=True,
    summary="Tracking view",
    responses={
        200: {"headers": {**RATE_LIMIT_SUCCESS_HEADERS, **ETAG_RESPONSE_HEADER}},
        304: {"description": "Not Modified", "headers": ETAG_RESPONSE_HEADER},
        429: {"description": "Rate limit exceeded", "headers": RATE_LIMIT_THROTTLED_HEADERS},
    },
)
def tracking_endpoint(
    public_tracking_id: str,
    response: Response,
    db: Session = Depends(get_db),
    rate_limit: RateLimitStatus = Depends(rate_limit_public_tracking),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> TrackingViewResponse | Response:
    assert_production_safe(order_id=public_tracking_id)
    apply_rate_limit_headers(
        response,
        limit=rate_limit.limit,
        remaining=rate_limit.remaining,
        reset_at_s=rate_limit.reset_at_s,
    )

    payload = build_public_tracking_payload(db, public_tracking_id)
    etag = build_public_tracking_etag(payload)
    response.headers["ETag"] = etag

    if etag_matches(if_none_match, etag):
        response.status_code = 304
        return response

    return TrackingViewResponse(**payload)
