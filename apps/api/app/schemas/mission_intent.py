import uuid

from pydantic import BaseModel


class MissionIntentSubmitResponse(BaseModel):
    order_id: uuid.UUID
    mission_intent_id: str
    status: str
