"""The pydantic models of the Script service: components/schemas of the OpenAPI file.

Request models validate what clients SEND (a broken payload -> automatic 422).
Response models filter what the service ANSWERS (only the fields of the spec, right types,
optional fields omitted instead of null).
The OpenAPI file  openapi/script-openapi-v1.0.yaml  is the contract: copy it faithfully.
"""
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CANDIDATE_PATTERN = r"^CN[0-9]{4}$"          # synthetic candidate numbers only, e.g. CN1042
COURSE_PATTERN = r"^[A-Z]{3}[0-9]{3}$"       # e.g. CSC201


class TransferStatus(StrEnum):
    """The three statuses of a custody transfer (PROVIDED)."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# ------------------------------------------------------------------ requests (task F1, F2)
class CreateBatchSchema(BaseModel):
    """Body of POST /v1/batches: components/schemas/CreateBatchSchema."""

    # TODO M2 (task F1): declare the three fields of CreateBatchSchema from the spec:
    #   course_code        str, must match COURSE_PATTERN                -> Field(pattern=...)
    #   session_label      str, 1 to 60 characters                       -> Field(min_length=..., max_length=...)
    #   candidate_numbers  list of str, 1 to 200 items, each item matching CANDIDATE_PATTERN
    #                      -> list[Annotated[str, Field(pattern=CANDIDATE_PATTERN)]] with Field(min_length=..., max_length=...)
    # Then add a @field_validator("candidate_numbers") that raises ValueError when the list contains duplicates.
    # Docs: docs/04_script_service_guide.md, step M2.1
    pass


class CreateTransferSchema(BaseModel):
    """Body of POST /v1/batches/{batch_id}/transfers: components/schemas/CreateTransferSchema."""

    # TODO M3 (task F2): one field, to_user_id, of type UUID (the person who will receive the scripts).
    pass


# ------------------------------------------------------------------ responses (task K1)
class ScriptSchema(BaseModel):
    """One script (paper) of a batch: components/schemas/ScriptSchema."""

    # TODO M1 (task K1): declare id (UUID), batch_id (UUID), candidate_number (str).
    # Until you do, this placeholder lets every stored field through, unchecked:
    model_config = ConfigDict(extra="allow")


class BatchSchema(BaseModel):
    """The representation of a batch: components/schemas/BatchSchema."""

    # TODO M1 (task K1): declare, in the order of the spec:
    #   id (UUID), course_code (str), session_label (str), script_count (int),
    #   created_by (UUID), current_custodian_id (UUID), created_at (datetime)
    # NOTE: the stored batch also holds the lists "scripts" and "transfers". The spec does NOT show
    # them in a batch, so they must NOT be declared here: that is how the model hides them.
    model_config = ConfigDict(extra="allow")


class TransferSchema(BaseModel):
    """One custody transfer: components/schemas/TransferSchema."""

    # TODO M1 (task K1): declare id, batch_id, from_user_id, to_user_id (all UUID), status (TransferStatus),
    # requested_at (datetime) and responded_at (datetime, OPTIONAL: `datetime | None = None`;
    # it is absent while the transfer is pending).
    model_config = ConfigDict(extra="allow")


class CustodianSchema(BaseModel):
    """Answer of GET /v1/batches/{batch_id}/custodian: components/schemas/CustodianSchema."""

    # TODO M1 (task K1): declare batch_id (UUID) and custodian_id (UUID).
    model_config = ConfigDict(extra="allow")


class BatchesSchema(BaseModel):
    """Body of GET /v1/batches: an object with the list under "batches"."""

    # TODO M1 (task K1): batches, a list of BatchSchema.
    model_config = ConfigDict(extra="allow")


class ScriptsSchema(BaseModel):
    """Body of GET /v1/batches/{batch_id}/scripts."""

    # TODO M1 (task K1): scripts, a list of ScriptSchema.
    model_config = ConfigDict(extra="allow")


class TransfersSchema(BaseModel):
    """Body of GET /v1/batches/{batch_id}/transfers."""

    # TODO M1 (task K1): transfers, a list of TransferSchema.
    model_config = ConfigDict(extra="allow")
