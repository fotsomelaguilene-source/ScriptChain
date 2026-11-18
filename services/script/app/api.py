"""The web layer: the eight path operations of the Script service v1.0.

Each function is ONE operation of openapi/script-openapi-v1.0.yaml (its operationId is the
first word of the docstring). A path operation has four parts:

    @router.post("/v1/batches", status_code=201, response_model=BatchSchema, ...)   <- the DECORATOR:
                                                          method, path, success code, response model
    def create_batch(payload: CreateBatchSchema, store: Store, user: ...):         <- the PARAMETERS:
                                                          body, path/query values, collaborators, caller
        ...                                                                         <- the BODY: talk to the store

Python rule you WILL meet: parameters WITHOUT a default value must come BEFORE parameters
with one (`limit: ... = 10`). Put `store`, the path values and the body first.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.errors import ServiceUnavailable, Unprocessable
from app.ports import DirectoryUnavailable, UserDirectory
from app.schemas import (BatchesSchema, BatchSchema, CreateBatchSchema, CreateTransferSchema,
                         CustodianSchema, ScriptsSchema, TransferSchema, TransfersSchema)
from app.security import User, current_user, require_roles
from app.store import ScriptStore

router = APIRouter()

RECEIVER_ROLE = "examiner"      # v1.0 decision: scripts are handed over to examiners (open question Q3)


def get_store(request: Request) -> ScriptStore:
    """The store of the application serving *request* (each app has its own: tests get a fresh one)."""
    return request.app.state.store


def get_directory(request: Request) -> UserDirectory:
    """The user directory of the application (a fake in the tests, the Auth service later)."""
    return request.app.state.directory


# Declare `store: Store` in a path operation and FastAPI passes the application's store.
Store = Annotated[ScriptStore, Depends(get_store)]
Directory = Annotated[UserDirectory, Depends(get_directory)]
AnyUser = Annotated[User, Depends(current_user)]                         # any logged-in role
Officer = Annotated[User, Depends(require_roles("exams_officer"))]       # only the exams officer
Handler = Annotated[User, Depends(require_roles("exams_officer", "examiner"))]   # people who can hold scripts
Examiner = Annotated[User, Depends(require_roles("examiner"))]


# TODO M3 (task F2): complete this helper. It is called by start_transfer BEFORE the store.
#   1. ask the directory: directory.get_user(str(user_id))     (it may raise DirectoryUnavailable)
#        DirectoryUnavailable  -> raise ServiceUnavailable("...")      (503, we fail closed)
#   2. user is None            -> raise Unprocessable("...")           (422: the receiver does not exist)
#   3. user["is_active"] false -> raise Unprocessable("...")
#   4. user["role"] != RECEIVER_ROLE -> raise Unprocessable("...")
def ensure_valid_receiver(directory: UserDirectory, user_id: UUID) -> None:
    # Get the receiver from the directory
    try:
        user = directory.get_user(str(user_id))
        
        # Check if user is None
        if user is None:
            raise Unprocessable("The user is not found")
        
        # Check if the user is active
        if user["is_active"] == False:
            raise Unprocessable("The current user is not active")
        
        # Check the user's role
        if user["role"] != RECEIVER_ROLE:
            raise Unprocessable("This user is unable to receive a transfer")
        
        return user
    except DirectoryUnavailable:
        raise ServiceUnavailable("The service is un available")
    
    # raise NotImplementedError("TODO M3: ensure_valid_receiver -- ask the directory; 503 / 422 as described")


# ---------------------------------------------------------------------- M1: reads
# TODO M1 (task K3): operation getBatches -- GET /v1/batches, success 200, response model BatchesSchema.
#   decorator: @router.get("/v1/batches", status_code=..., response_model=BatchesSchema, response_model_exclude_none=True)
#   parameters (no default first!): store: Store, user: AnyUser,
#       course_code: Annotated[str | None, Query(pattern=COURSE_PATTERN-like)] = None,
#       limit: Annotated[int, Query(ge=1, le=100)] = 10,  offset: Annotated[int, Query(ge=0)] = 0
#   body: return {"batches": store.list_batches(course_code=..., limit=..., offset=...)}
#   (the answer is an OBJECT with a list inside, not a bare list -- the spec says so)
def list_batches():
    raise NotImplementedError("TODO M1: list_batches -- write the decorator, the parameters and the body")


@router.get("/v1/batches/{batch_id}", status_code=status.HTTP_200_OK, response_model=BatchSchema,
            response_model_exclude_none=True)
def get_batch(batch_id: UUID, store: Store, user: AnyUser):
    """getBatch: the batch with this id; 404 when there is none."""
    # TODO M1 (task K3): the decorator and the parameters above are GIVEN (worked example).
    # Write the body only: one line -- return what store.get_batch(batch_id) gives.
    raise NotImplementedError("TODO M1: get_batch -- return store.get_batch(batch_id)")


# TODO M1 (task K3): operation getScripts -- GET /v1/batches/{batch_id}/scripts, 200, response model ScriptsSchema.
#   path value batch_id: UUID; query limit (1-100, default 10) and offset (>= 0, default 0); caller: any role.
#   body: return {"scripts": store.list_scripts(batch_id, limit=limit, offset=offset)}
def get_scripts():
    raise NotImplementedError("TODO M1: get_scripts -- write the decorator, the parameters and the body")


# TODO M1 (task K3): operation getTransfers -- GET /v1/batches/{batch_id}/transfers, 200, response model TransfersSchema.
#   path value batch_id: UUID; caller: any role. body: return {"transfers": store.list_transfers(batch_id)}
def get_transfers():
    raise NotImplementedError("TODO M1: get_transfers -- write the decorator, the parameters and the body")


# TODO M1 (task K3): operation getCustodian -- GET /v1/batches/{batch_id}/custodian, 200, response model CustodianSchema.
#   This is THE call the Mark service will make. body: return {"batch_id": batch_id, "custodian_id": store.custodian_of(batch_id)}
def get_custodian():
    raise NotImplementedError("TODO M1: get_custodian -- write the decorator, the parameters and the body")


# ---------------------------------------------------------------------- M2: create a batch
# TODO M2 (task F1): operation createBatch -- POST /v1/batches, success 201 (status.HTTP_201_CREATED), response model BatchSchema.
#   parameters: payload: CreateBatchSchema, store: Store, user: Officer   (only the exams officer creates batches)
#   body: payload.model_dump(mode="json") turns the validated body into a plain dict;
#         return store.create_batch(that_dict, created_by=user.id)
@router.post('/v1/batches',
             status_code=status.HTTP_201_CREATED,
             response_model=BatchSchema)
def create_batch(payload:CreateBatchSchema,store:Store,user:Officer):
    
    body = payload.model_dump(mode="json")
    
    return store.create_batch(body,created_by=user.id)
    # raise NotImplementedError("TODO M2: create_batch -- write the decorator, the parameters and the body")


# ---------------------------------------------------------------------- M3: custody transfers
# TODO M3 (task F2): operation startTransfer -- POST /v1/batches/{batch_id}/transfers, 201, response model TransferSchema.
#   parameters: batch_id: UUID, payload: CreateTransferSchema, store: Store, directory: Directory, user: Handler
#   body: 1) ensure_valid_receiver(directory, payload.to_user_id)   2) return store.request_transfer(batch_id, payload.to_user_id, user.id)
@router.post('/v1/batches/{batch_id}/transfers',
             status_code=status.HTTP_201_CREATED,
             response_model=TransferSchema)
def start_transfer(batch_id: UUID,
                   payload: CreateTransferSchema,
                   store: Store,
                   directory: Directory,
                   user: Handler):
    
    
    raise NotImplementedError("TODO M3: start_transfer -- write the decorator, the parameters and the body")


# TODO M3 (task F2): operation acceptTransfer -- POST /v1/transfers/{transfer_id}/accept, 200, response model TransferSchema.
#   parameters: transfer_id: UUID, store: Store, user: Examiner. body: return store.accept_transfer(transfer_id, user.id)
def accept_transfer():
    raise NotImplementedError("TODO M3: accept_transfer -- write the decorator, the parameters and the body")
