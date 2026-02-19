import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.fleet_api_client import FleetApiClientProtocol, get_fleet_api_client
from app.integrations.gcs_bridge_client import MissionPublisherProtocol, get_gcs_bridge_client
from app.models.order import OrderStatus
from app.schemas.dispatch import ManualAssignRequest, ManualAssignResponse
from app.schemas.events import DeliveryEventListResponse, DeliveryEventResponse
from app.schemas.mission_intent import MissionIntentSubmitResponse
from app.schemas.order import OrderCancelResponse, OrderCreate, OrderListResponse, OrderResponse
from app.schemas.pod import ProofOfDeliveryCreate, ProofOfDeliveryResponse
from app.services.dispatch_service import manual_assign_order
from app.services.mission_intent_service import submit_mission_intent
from app.services.orders_service import (
    cancel_order,
    create_order,
    get_order,
    list_order_events,
    list_orders,
)
from app.services.pod_service import create_proof_of_delivery

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order_endpoint(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderResponse:
    order = create_order(db, payload)
    return OrderResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_endpoint(order_id: uuid.UUID, db: Session = Depends(get_db)) -> OrderResponse:
    order = get_order(db, order_id)
    return OrderResponse.model_validate(order)


@router.get("", response_model=OrderListResponse)
def list_orders_endpoint(
    status: OrderStatus | None = Query(default=None), db: Session = Depends(get_db)
) -> OrderListResponse:
    items = [OrderResponse.model_validate(order) for order in list_orders(db, status)]
    return OrderListResponse(items=items)


@router.post("/{order_id}/cancel", response_model=OrderCancelResponse)
def cancel_order_endpoint(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrderCancelResponse:
    order = cancel_order(db, order_id)
    return OrderCancelResponse(id=order.id, status=order.status)


@router.post("/{order_id}/assign", response_model=ManualAssignResponse)
def manual_assign_order_endpoint(
    order_id: uuid.UUID,
    payload: ManualAssignRequest,
    db: Session = Depends(get_db),
    fleet_client: FleetApiClientProtocol = Depends(get_fleet_api_client),
) -> ManualAssignResponse:
    job = manual_assign_order(db, fleet_client, order_id, payload.drone_id)
    return ManualAssignResponse(
        order_id=job.order_id,
        assigned_drone_id=job.assigned_drone_id or "",
    )


@router.post("/{order_id}/submit-mission-intent", response_model=MissionIntentSubmitResponse)
def submit_mission_intent_endpoint(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    publisher: MissionPublisherProtocol = Depends(get_gcs_bridge_client),
) -> MissionIntentSubmitResponse:
    order, job, _intent = submit_mission_intent(db, publisher, order_id)
    return MissionIntentSubmitResponse(
        order_id=order.id,
        mission_intent_id=job.mission_intent_id or "",
        status=order.status.value,
    )


@router.post("/{order_id}/pod", response_model=ProofOfDeliveryResponse)
def create_pod_endpoint(
    order_id: uuid.UUID,
    payload: ProofOfDeliveryCreate,
    db: Session = Depends(get_db),
) -> ProofOfDeliveryResponse:
    pod = create_proof_of_delivery(db, order_id, payload)
    return ProofOfDeliveryResponse(
        id=pod.id,
        order_id=pod.order_id,
        method=pod.method,
        photo_url=pod.photo_url,
        confirmed_by=pod.confirmed_by,
        created_at=pod.created_at,
    )


@router.get("/{order_id}/events", response_model=DeliveryEventListResponse)
def list_order_events_endpoint(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DeliveryEventListResponse:
    events = [
        DeliveryEventResponse.model_validate(event)
        for event in list_order_events(db, order_id)
    ]
    return DeliveryEventListResponse(items=events)
