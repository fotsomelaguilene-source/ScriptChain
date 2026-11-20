"""The pydantic models of the Mark service: components/schemas of the OpenAPI file.

Request models validate what clients SEND (a broken payload -> automatic 422).
Response models filter what the service ANSWERS (only the fields of the spec, right types).
The OpenAPI file  openapi/mark-openapi-v1.0.yaml  is the contract: copy it faithfully.
"""
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CANDIDATE_PATTERN = r"^CN[0-9]{4}$"
Score = Annotated[float, Field(strict=True, ge=0, le=100)]    # strict: "50" and true are refused; 50 and 50.5 are fine


class BatchMarkStatus(StrEnum):
    """Where the marks of a batch stand (PROVIDED)."""

    ENTERED = "entered"
    IN_MODERATION = "in_moderation"
    APPROVED = "approved"


# ------------------------------------------------------------------ requests (task F3, F4)
class MarkEntrySchema(BaseModel):
    """One mark in a bulk submission: components/schemas/MarkEntrySchema."""

    candidate_number: str = Field(..., pattern=CANDIDATE_PATTERN)
    score: Score


class BulkMarksSchema(BaseModel):
    """Body of POST /v1/batches/{batch_id}/marks/bulk: components/schemas/BulkMarksSchema."""

    entries: list[MarkEntrySchema] = Field(..., min_length=1, max_length=500)

    @field_validator("entries")
    @classmethod
    def no_same_candidate(cls, value):
        # A candidate cannot appear two times in the same request
        seen = []
        for entry in value:
            if entry.candidate_number in seen:
                raise ValueError("A candidate can appear only once")
            seen.append(entry.candidate_number)
        return value


class AdjustmentRequestSchema(BaseModel):
    """Body of POST /v1/marks/{mark_id}/adjustments: components/schemas/AdjustmentRequestSchema."""

    model_config = ConfigDict(str_strip_whitespace=True)       # "   " becomes "" and then fails min_length=1

    new_score: Score
    reason: str = Field(..., min_length=1, max_length=500)


# ------------------------------------------------------------------ responses (task K1)
# The stored mark also has a list "adjustments", it is not declared here so it is not shown.
class MarkSchema(BaseModel):
    """One mark: components/schemas/MarkSchema."""

    id: UUID
    batch_id: UUID
    candidate_number: str
    original_score: float
    current_score: float
    entered_by: UUID
    custodian_id_at_entry: UUID
    entered_at: datetime


class MarksSchema(BaseModel):
    """Body of GET /v1/batches/{batch_id}/marks."""

    marks: list[MarkSchema]


class BulkResultSchema(BaseModel):
    """Answer of POST /v1/batches/{batch_id}/marks/bulk."""

    batch_id: UUID
    status: BatchMarkStatus
    marks: list[MarkSchema]


class AdjustmentSchema(BaseModel):
    """One change of a mark by a moderator: components/schemas/AdjustmentSchema."""

    id: UUID
    mark_id: UUID
    old_score: float
    new_score: float
    reason: str
    adjusted_by: UUID
    adjusted_at: datetime


class AdjustmentsSchema(BaseModel):
    """Body of GET /v1/marks/{mark_id}/adjustments."""

    adjustments: list[AdjustmentSchema]


class PendingBatchSchema(BaseModel):
    """One line of the moderation queue: components/schemas/PendingBatchSchema."""

    batch_id: UUID
    status: BatchMarkStatus
    mark_count: int


class PendingSchema(BaseModel):
    """Body of GET /v1/moderation/pending."""

    batches: list[PendingBatchSchema]


class ApprovalSchema(BaseModel):
    """The approval of a batch by the head of department: components/schemas/ApprovalSchema."""

    id: UUID
    batch_id: UUID
    approved_by: UUID
    approved_at: datetime
