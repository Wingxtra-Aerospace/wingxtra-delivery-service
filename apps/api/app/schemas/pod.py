import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.proof_of_delivery import ProofOfDeliveryMethod


class ProofOfDeliveryCreate(BaseModel):
    method: ProofOfDeliveryMethod
    photo_url: str | None = Field(default=None, max_length=1024)
    otp_code: str | None = Field(default=None, min_length=4, max_length=32)
    confirmed_by: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict = Field(default_factory=dict)


class ProofOfDeliveryResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    method: ProofOfDeliveryMethod
    photo_url: str | None
    confirmed_by: str | None
    created_at: datetime


class PublicPodSummary(BaseModel):
    method: ProofOfDeliveryMethod
    photo_url: str | None
    created_at: datetime
