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

    # TODO M2 (task F3): candidate_number (str matching CANDIDATE_PATTERN) and score (use the ready-made `Score` type above).
    pass


class BulkMarksSchema(BaseModel):
    """Body of POST /v1/batches/{batch_id}/marks/bulk: components/schemas/BulkMarksSchema."""

    # TODO M2 (task F3): entries, a list of MarkEntrySchema with 1 to 500 items; plus a @field_validator("entries")
    # that raises ValueError when two entries have the same candidate_number.
    pass


class AdjustmentRequestSchema(BaseModel):
    """Body of POST /v1/marks/{mark_id}/adjustments: components/schemas/AdjustmentRequestSchema."""

    # TODO M3 (task F4): new_score (the ready-made `Score` type) and reason (str, 1 to 500 characters AFTER removing
    # the spaces around it: add  model_config = ConfigDict(str_strip_whitespace=True)  so that "   " becomes "" and
    # fails min_length=1).
    pass


# ------------------------------------------------------------------ responses (task K1)
class MarkSchema(BaseModel):
    """One mark: components/schemas/MarkSchema."""

    # TODO M1 (task K1): in the order of the spec: id (UUID), batch_id (UUID), candidate_number (str),
    # original_score (float), current_score (float), entered_by (UUID), custodian_id_at_entry (UUID),
    # entered_at (datetime). The stored mark also holds a list "adjustments": the spec does NOT show it in a
    # mark, so do not declare it.
    model_config = ConfigDict(extra="allow")


class MarksSchema(BaseModel):
    """Body of GET /v1/batches/{batch_id}/marks."""

    # TODO M1 (task K1): marks, a list of MarkSchema.
    model_config = ConfigDict(extra="allow")


class BulkResultSchema(BaseModel):
    """Answer of POST /v1/batches/{batch_id}/marks/bulk."""

    # TODO M1 (task K1): batch_id (UUID), status (BatchMarkStatus), marks (a list of MarkSchema).
    model_config = ConfigDict(extra="allow")


class AdjustmentSchema(BaseModel):
    """One change of a mark by a moderator: components/schemas/AdjustmentSchema."""

    # TODO M1 (task K1): id (UUID), mark_id (UUID), old_score (float), new_score (float), reason (str),
    # adjusted_by (UUID), adjusted_at (datetime).
    model_config = ConfigDict(extra="allow")


class AdjustmentsSchema(BaseModel):
    """Body of GET /v1/marks/{mark_id}/adjustments."""

    # TODO M1 (task K1): adjustments, a list of AdjustmentSchema.
    model_config = ConfigDict(extra="allow")


class PendingBatchSchema(BaseModel):
    """One line of the moderation queue: components/schemas/PendingBatchSchema."""

    # TODO M1 (task K1): batch_id (UUID), status (BatchMarkStatus), mark_count (int).
    model_config = ConfigDict(extra="allow")


class PendingSchema(BaseModel):
    """Body of GET /v1/moderation/pending."""

    # TODO M1 (task K1): batches, a list of PendingBatchSchema.
    model_config = ConfigDict(extra="allow")


class ApprovalSchema(BaseModel):
    """The approval of a batch by the head of department: components/schemas/ApprovalSchema."""

    # TODO M1 (task K1): id (UUID), batch_id (UUID), approved_by (UUID), approved_at (datetime).
    model_config = ConfigDict(extra="allow")
