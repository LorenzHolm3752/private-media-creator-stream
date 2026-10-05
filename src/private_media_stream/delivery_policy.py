from enum import StrEnum

from pydantic import BaseModel, Field


class ProcessingState(StrEnum):
    INGESTED = "ingested"
    PROCESSING = "processing"
    READY = "ready"


class CreatorRequest(BaseModel):
    delivery_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    asset_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    processing_state: ProcessingState
    approved_for_creator_delivery: bool
    redacted_transcript: str = Field(min_length=1, max_length=12_000)
    creator_instruction: str = Field(min_length=1, max_length=500)


class DeliveryDecision(BaseModel):
    allowed: bool
    reason: str


def decide_delivery(request: CreatorRequest) -> DeliveryDecision:
    if request.processing_state is not ProcessingState.READY:
        return DeliveryDecision(allowed=False, reason="Asset processing is not complete")
    if not request.approved_for_creator_delivery:
        return DeliveryDecision(allowed=False, reason="Creator delivery is not approved")
    return DeliveryDecision(allowed=True, reason="Asset is ready for creator delivery")
