import uuid

from pydantic import BaseModel


class DispatchRunResponseItem(BaseModel):
    order_id: uuid.UUID
    assigned_drone_id: str


class DispatchRunResponse(BaseModel):
    assignments: list[DispatchRunResponseItem]


class ManualAssignRequest(BaseModel):
    drone_id: str


class ManualAssignResponse(BaseModel):
    order_id: uuid.UUID
    assigned_drone_id: str
