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
@router.get("/v1/batches/{batch_id}/marks",
            status_code=status.HTTP_200_OK,
            response_model=MarksSchema)
def get_marks(batch_id: UUID,
              store: Store,
              user: AnyUser,
              limit: Annotated[int, Query(ge=1, le=100)] = 10,
              offset: Annotated[int, Query(ge=0)] = 0):

    return {"marks": store.list_marks(batch_id, limit=limit, offset=offset)}


@router.get("/v1/marks/{mark_id}",
            status_code=status.HTTP_200_OK,
            response_model=MarkSchema)
def get_mark(mark_id: UUID, store: Store, user: AnyUser):

    return store.get_mark(mark_id)


@router.get("/v1/marks/{mark_id}/adjustments",
            status_code=status.HTTP_200_OK,
            response_model=AdjustmentsSchema)
def get_adjustments(mark_id: UUID, store: Store, user: AnyUser):

    return {"adjustments": store.list_adjustments(mark_id)}


@router.get("/v1/moderation/pending",
            status_code=status.HTTP_200_OK,
            response_model=PendingSchema)
def get_pending(store: Store, user: ModeratorOrHod):

    return {"batches": store.pending()}


@router.get("/v1/batches/{batch_id}/approval",
            status_code=status.HTTP_200_OK,
            response_model=ApprovalSchema)
def get_approval(batch_id: UUID, store: Store, user: AnyUser):

    return store.get_approval(batch_id)


# ---------------------------------------------------------------------- M2: bulk submission
@router.post("/v1/batches/{batch_id}/marks/bulk",
             status_code=status.HTTP_201_CREATED,
             response_model=BulkResultSchema)
def submit_marks(batch_id: UUID,
                 payload: BulkMarksSchema,
                 store: Store,
                 custodians: Custodians,
                 user: Examiner,
                 idempotency_key: IdempotencyKey):

    # 1. Fingerprint of the request
    body = payload.model_dump(mode="json")
    digest = fingerprint(batch_id, user.id, body)

    # 2. Look for the Idempotency-Key (before the custodian check, so a retry works even if Script is down)
    previous = store.find_idempotent(idempotency_key)
    if previous is not None:
        # Same key but another request
        if previous["fingerprint"] != digest:
            raise Unprocessable(message="This Idempotency-Key was already used for another request")
        # Same key and same request: give the first answer again
        return previous["response"]

    # 3. Ask the Script service who is the custodian
    try:
        custodian_id = custodians.get_custodian(str(batch_id), user.token)
    except BatchNotFound:
        raise NotFound(message="The Script service does not know this batch")
    except ScriptServiceUnavailable:
        raise ServiceUnavailable(message="The Script service is not available, the marks are not saved")

    # 4. Only the custodian can submit the marks
    if custodian_id != user.id:
        raise Conflict(message="Only the current custodian of the batch can submit its marks")

    # 5. Save the marks
    result = store.submit_marks(str(batch_id), body["entries"], user.id, custodian_id)

    # 6. Remember the answer for a retry
    store.remember(idempotency_key, digest, result)

    return result


# ---------------------------------------------------------------------- M3: moderation and approval
@router.post("/v1/marks/{mark_id}/adjustments",
             status_code=status.HTTP_201_CREATED,
             response_model=AdjustmentSchema)
def adjust_mark(mark_id: UUID, payload: AdjustmentRequestSchema, store: Store, user: Moderator):

    return store.add_adjustment(mark_id, payload.new_score, payload.reason, user.id)


@router.post("/v1/batches/{batch_id}/approval",
             status_code=status.HTTP_201_CREATED,
             response_model=ApprovalSchema)
def approve_batch(batch_id: UUID, store: Store, user: Hod):

    return store.approve(batch_id, user.id)
