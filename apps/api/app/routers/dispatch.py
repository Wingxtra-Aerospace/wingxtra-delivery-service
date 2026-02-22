from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext, require_roles
from app.db.session import get_db
from app.observability import metrics_store, observe_timing
from app.schemas.ui import DispatchRunRequest, DispatchRunResponse
from app.services.idempotency_service import (
    build_scope,
    check_idempotency,
    save_idempotency_result,
    validate_idempotency_key,
)
from app.services.safety import assert_production_safe
from app.services.ui_service import run_auto_dispatch

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])


@router.post(
    "/run",
    response_model=DispatchRunResponse,
    summary="Run auto dispatch",
)
def run_dispatch_endpoint(
    request: DispatchRunRequest = Body(default_factory=DispatchRunRequest),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> DispatchRunResponse:
    assert_production_safe()
    request_payload = request.model_dump(mode="json", exclude_none=True)
    route_scope = build_scope("POST:/api/v1/dispatch/run", user_id=auth.user_id)
    idempotency_key = validate_idempotency_key(idempotency_key)

    if idempotency_key:
        idem = check_idempotency(
            db=db,
            user_id=auth.user_id,
            route=route_scope,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if idem.replay and idem.response_payload:
            return DispatchRunResponse.model_validate(idem.response_payload)

    with observe_timing("dispatch_run_seconds"):
        response_payload = DispatchRunResponse.model_validate(
            run_auto_dispatch(auth, db, max_assignments=request.max_assignments)
        ).model_dump(mode="json")
    metrics_store.increment("dispatch_run_total")

    if idempotency_key:
        save_idempotency_result(
            db=db,
            user_id=auth.user_id,
            route=route_scope,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            response_payload=response_payload,
        )

    return DispatchRunResponse.model_validate(response_payload)
