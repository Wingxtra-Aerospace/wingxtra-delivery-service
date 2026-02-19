from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.fleet_api_client import FleetApiClientProtocol, get_fleet_api_client
from app.schemas.dispatch import DispatchRunResponse, DispatchRunResponseItem
from app.services.dispatch_service import run_auto_dispatch

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])


@router.post("/run", response_model=DispatchRunResponse)
def run_dispatch_endpoint(
    db: Session = Depends(get_db),
    fleet_client: FleetApiClientProtocol = Depends(get_fleet_api_client),
) -> DispatchRunResponse:
    assignments = run_auto_dispatch(db, fleet_client)
    return DispatchRunResponse(
        assignments=[
            DispatchRunResponseItem(
                order_id=order.id,
                assigned_drone_id=job.assigned_drone_id or "",
            )
            for order, job in assignments
        ]
    )
