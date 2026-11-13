"""The web layer: the eight path operations of the Mark service v1.0.

Same anatomy as the Script service (decorator / parameters / body -- see its api.py).
New here: a HEADER parameter (Idempotency-Key) and a second collaborator, the custodian client.

    idempotency_key: Annotated[str, Header(min_length=8, max_length=100)]

FastAPI turns the Python name idempotency_key into the header name Idempotency-Key.
"""
import hashlib
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.errors import Conflict, NotFound, ServiceUnavailable, Unprocessable
from app.ports import BatchNotFound, CustodianClient, ScriptServiceUnavailable
from app.schemas import (AdjustmentRequestSchema, AdjustmentSchema, AdjustmentsSchema, ApprovalSchema,
                         BulkMarksSchema, BulkResultSchema, MarkSchema, MarksSchema, PendingSchema)
from app.security import User, current_user, require_roles
from app.store import MarkStore

router = APIRouter()


def get_store(request: Request) -> MarkStore:
    """The store of the application serving *request*."""
    return request.app.state.store


def get_custodians(request: Request) -> CustodianClient:
    """The client that asks the Script service who the custodian is (a fake in the tests)."""
    return request.app.state.custodians


Store = Annotated[MarkStore, Depends(get_store)]
Custodians = Annotated[CustodianClient, Depends(get_custodians)]
AnyUser = Annotated[User, Depends(current_user)]
Examiner = Annotated[User, Depends(require_roles("examiner"))]
Moderator = Annotated[User, Depends(require_roles("moderator"))]
ModeratorOrHod = Annotated[User, Depends(require_roles("moderator", "hod"))]
Hod = Annotated[User, Depends(require_roles("hod"))]
IdempotencyKey = Annotated[str, Header(min_length=8, max_length=100)]


def fingerprint(batch_id: UUID, user_id: str, body: dict) -> str:
    """PROVIDED. A short signature of "who sent which marks for which batch": two identical requests have the
    same fingerprint, two different ones (even by one mark) do not. Used for the Idempotency-Key rule."""
    raw = json.dumps({"batch_id": str(batch_id), "user": user_id, "body": body}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------- M1: reads
# TODO M1 (task K3): operation getMarks -- GET /v1/batches/{batch_id}/marks, 200, response model MarksSchema.
#   parameters: batch_id: UUID, store: Store, user: AnyUser, limit (1-100, default 10), offset (>= 0, default 0)
#   body: return {"marks": store.list_marks(batch_id, limit=limit, offset=offset)}
def get_marks():
    raise NotImplementedError("TODO M1: get_marks -- write the decorator, the parameters and the body")


# TODO M1 (task K3): operation getMark -- GET /v1/marks/{mark_id}, 200, response model MarkSchema.
#   The decorator and the parameters are the same kind as above; body: return store.get_mark(mark_id)
def get_mark():
    raise NotImplementedError("TODO M1: get_mark -- write the decorator, the parameters and the body")


# TODO M1 (task K3): operation getAdjustments -- GET /v1/marks/{mark_id}/adjustments, 200, response model AdjustmentsSchema.
#   body: return {"adjustments": store.list_adjustments(mark_id)}
def get_adjustments():
    raise NotImplementedError("TODO M1: get_adjustments -- write the decorator, the parameters and the body")


# TODO M1 (task K3): operation getPending -- GET /v1/moderation/pending, 200, response model PendingSchema.
#   caller: ModeratorOrHod (ready-made alias above: only moderator and hod). body: return {"batches": store.pending()}
def get_pending():
    raise NotImplementedError("TODO M1: get_pending -- write the decorator, the parameters and the body")


# TODO M1 (task K3): operation getApproval -- GET /v1/batches/{batch_id}/approval, 200, response model ApprovalSchema.
#   body: return store.get_approval(batch_id)
def get_approval():
    raise NotImplementedError("TODO M1: get_approval -- write the decorator, the parameters and the body")


# ---------------------------------------------------------------------- M2: bulk submission
# TODO M2 (task F3): operation submitMarks -- POST /v1/batches/{batch_id}/marks/bulk, success 201, response model BulkResultSchema.
#   parameters: batch_id: UUID, payload: BulkMarksSchema, store: Store, custodians: Custodians, user: Examiner,
#               idempotency_key: IdempotencyKey            (all without default, so no problem with the order)
#   body, in THIS order:
#     1. body = payload.model_dump(mode="json");  digest = fingerprint(batch_id, user.id, body)
#     2. previous = store.find_idempotent(idempotency_key)
#          - if previous exists and previous["fingerprint"] != digest -> raise Unprocessable(...)  (key reused for another request)
#          - if previous exists and it is the same request            -> return previous["response"]  (a retry: same answer, nothing saved twice)
#     3. ask the custodian: try: custodian_id = custodians.get_custodian(str(batch_id), user.token)
#          except BatchNotFound -> raise NotFound(...)            except ScriptServiceUnavailable -> raise ServiceUnavailable(...)  (fail closed)
#     4. if custodian_id != user.id -> raise Conflict("Only the current custodian ...")
#     5. result = store.submit_marks(str(batch_id), body["entries"], user.id, custodian_id)
#     6. store.remember(idempotency_key, digest, result);  return result
def submit_marks():
    raise NotImplementedError("TODO M2: submit_marks -- write the decorator, the parameters and the body")


# ---------------------------------------------------------------------- M3: moderation and approval
# TODO M3 (task F4): operation adjustMark -- POST /v1/marks/{mark_id}/adjustments, success 201, response model AdjustmentSchema.
#   parameters: mark_id: UUID, payload: AdjustmentRequestSchema, store: Store, user: Moderator
#   body: return store.add_adjustment(mark_id, payload.new_score, payload.reason, user.id)
def adjust_mark():
    raise NotImplementedError("TODO M3: adjust_mark -- write the decorator, the parameters and the body")


# TODO M3 (task F4): operation approveBatch -- POST /v1/batches/{batch_id}/approval, success 201, response model ApprovalSchema.
#   parameters: batch_id: UUID, store: Store, user: Hod.   body: return store.approve(batch_id, user.id)
def approve_batch():
    raise NotImplementedError("TODO M3: approve_batch -- write the decorator, the parameters and the body")
