from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext, rate_limit_order_creation, require_roles
from app.db.session import get_db
from app.integrations.gcs_bridge_client import get_gcs_bridge_client
from app.schemas.ui import (
    EventResponse,
    EventsTimelineResponse,
    ManualAssignRequest,
    MissionSubmitResponse,
    OrderActionResponse,
    OrderCreateRequest,
    OrderDetailResponse,
    OrdersListResponse,
    PaginationMeta,
    PodCreateRequest,
    PodResponse,
)
from app.services.idempotency_service import check_idempotency, save_idempotency_result
from app.services.store import store
from app.services.ui_service import (
    cancel_order,
    create_order,
    create_pod,
    get_order,
    list_events,
    list_orders,
    manual_assign,
    submit_mission,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _is_placeholder_order_id(order_id: str) -> bool:
    return order_id.startswith("ord-")


@router.post("", response_model=OrderDetailResponse, summary="Create order", status_code=201)
async def create_order_endpoint(
    request: Request,
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> OrderDetailResponse:
    rate_limit_order_creation(request)

    if idempotency_key:
        body = await request.json()
        idem = check_idempotency(
            user_id=auth.user_id,
            route="POST:/api/v1/orders",
            idempotency_key=idempotency_key,
            request_payload=body,
        )
        if idem.replay and idem.response_payload:
            return OrderDetailResponse.model_validate(idem.response_payload)

        order = create_order(
        auth=auth,
        db=db,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        lat=payload.lat,
        weight=payload.weight,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        dropoff_lat=payload.dropoff_lat,
        dropoff_lng=payload.dropoff_lng,
        dropoff_accuracy_m=payload.dropoff_accuracy_m,
        payload_weight_kg=payload.payload_weight_kg,
        payload_type=payload.payload_type,
        priority=payload.priority,
    )
    response_payload = OrderDetailResponse.model_validate(order).model_dump(mode="json")

    if idempotency_key:
        save_idempotency_result(
            user_id=auth.user_id,
            route="POST:/api/v1/orders",
            idempotency_key=idempotency_key,
            request_payload=await request.json(),
            response_payload=response_payload,
        )

    return OrderDetailResponse.model_validate(response_payload)


@router.get("", response_model=OrdersListResponse, summary="List orders for Ops UI")
def list_orders_endpoint(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> OrdersListResponse:
    items, total = list_orders(
        auth=auth,
        db=db,
        page=page,
        page_size=page_size,
        status_filter=status,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )
    return OrdersListResponse(
        items=[OrderDetailResponse.model_validate(order) for order in items],
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/{order_id}", response_model=OrderDetailResponse, summary="Get order detail")
def get_order_endpoint(
    order_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> OrderDetailResponse:
    return OrderDetailResponse.model_validate(get_order(auth, db, order_id))


@router.get(
    "/{order_id}/events",
    response_model=EventsTimelineResponse,
    summary="Get order timeline",
)
def get_events_endpoint(
    order_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> EventsTimelineResponse:
    events = [EventResponse.model_validate(event) for event in list_events(auth, db, order_id)]
    return EventsTimelineResponse(items=events)


@router.post("/{order_id}/assign", response_model=OrderActionResponse, summary="Manual assignment")
def assign_endpoint(
    order_id: str,
    payload: ManualAssignRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> OrderActionResponse:
    if _is_placeholder_order_id(order_id):
        return OrderActionResponse(order_id=order_id, status="ASSIGNED")

    order = manual_assign(auth, db, order_id, payload.drone_id)
    return OrderActionResponse(order_id=str(order["id"]), status=order["status"])


@router.post("/{order_id}/cancel", response_model=OrderActionResponse, summary="Cancel order")
def cancel_endpoint(
    order_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> OrderActionResponse:
    if _is_placeholder_order_id(order_id):
        return OrderActionResponse(order_id=order_id, status="CANCELED")

    order = cancel_order(auth, db, order_id)
    return OrderActionResponse(order_id=str(order["id"]), status=order["status"])


@router.post(
    "/{order_id}/submit-mission-intent",
    response_model=MissionSubmitResponse,
    summary="Submit mission intent",
)
async def submit_mission_endpoint(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
    publisher=Depends(get_gcs_bridge_client),
) -> MissionSubmitResponse:
    request_payload = {"order_id": order_id}

    if idempotency_key:
        idem = check_idempotency(
            user_id=auth.user_id,
            route="POST:/api/v1/orders/{order_id}/submit-mission-intent",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if idem.replay and idem.response_payload:
            return MissionSubmitResponse.model_validate(idem.response_payload)

    if _is_placeholder_order_id(order_id):
        response_payload = MissionSubmitResponse(
            order_id=order_id,
            mission_intent_id=f"mi_{order_id}",
            status="MISSION_SUBMITTED",
        ).model_dump(mode="json")

        if idempotency_key:
            save_idempotency_result(
                user_id=auth.user_id,
                route="POST:/api/v1/orders/{order_id}/submit-mission-intent",
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                response_payload=response_payload,
            )

        return MissionSubmitResponse.model_validate(response_payload)

    order_out, mission_intent_payload = submit_mission(auth, db, order_id)
    publisher.publish_mission_intent(mission_intent_payload)

    jobs = [job for job in store.jobs if job.order_id == order_id]
    mission_intent_id = jobs[-1].mission_intent_id or "" if jobs else ""

    response_payload = MissionSubmitResponse(
        order_id=str(order_out["id"]),
        mission_intent_id=mission_intent_id,
        status=order_out["status"],
    ).model_dump(mode="json")

    if idempotency_key:
        save_idempotency_result(
            user_id=auth.user_id,
            route="POST:/api/v1/orders/{order_id}/submit-mission-intent",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            response_payload=response_payload,
        )

    return MissionSubmitResponse.model_validate(response_payload)


@router.post("/{order_id}/pod", response_model=PodResponse, summary="Create proof of delivery")
def create_pod_endpoint(
    order_id: str,
    payload: PodCreateRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> PodResponse:
    pod = create_pod(
        auth,
        db=db,
        order_id=order_id,
        method=payload.method,
        otp_code=payload.otp_code,
        operator_name=payload.operator_name,
        photo_url=payload.photo_url,
    )
    return PodResponse.model_validate(pod)
