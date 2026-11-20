"""The in-memory store of the Script service: the only place where its data lives.

A batch is stored as a dict shaped like data/seed.json. It CONTAINS its scripts and its
transfers (the "aggregate" of the class diagram), so a stored batch looks like:

    {"id": "...", "course_code": "CSC201", "session_label": "...", "script_count": 4,
     "created_by": "<user id>", "current_custodian_id": "<user id>", "created_at": "2026-10-20T08:00:00Z",
     "scripts":   [{"id", "batch_id", "candidate_number"}, ...],
     "transfers": [{"id", "batch_id", "from_user_id", "to_user_id", "status", "requested_at",
                    "responded_at" (only once resolved)}, ...]}

Rules of the house:
* ids are plain strings (the UUID as text); timestamps are strings like "2026-10-20T08:00:00Z".
* the store hands out DEEP COPIES (copy.deepcopy): a caller changes a batch only through a method.
* the store raises errors from app/errors.py (NotFound, Conflict, Unprocessable); it never builds HTTP.
* everything is lost when the process stops; the seed comes back.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.clock import new_uuid, stamp, utc_now
from app.errors import Conflict, NotFound, Unprocessable

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed.json"


class ScriptStore:
    """A list of batch records with the operations the API needs."""

    def __init__(self, batches: Iterable[dict] = (), *,
                 clock: Callable[[], datetime] = utc_now,
                 new_id: Callable[[], UUID] = new_uuid) -> None:
        self._batches: list[dict] = [copy.deepcopy(batch) for batch in batches]
        self.clock = clock
        self.new_id = new_id

    @classmethod
    def from_seed(cls, path: Path = SEED_PATH, **kwargs) -> ScriptStore:
        with path.open(encoding="utf-8") as fh:
            return cls(json.load(fh), **kwargs)

    def __len__(self) -> int:
        return len(self._batches)

    # ------------------------------------------------------------------ PROVIDED helper
    def _find_batch(self, batch_id: object) -> dict:
        """The stored record (NOT a copy) of a batch; NotFound when there is none.

        This is a *worked example*: read it, then write the other methods in the same style.
        """
        for batch in self._batches:
            if batch["id"] == str(batch_id):
                return batch
        raise NotFound(f"Batch {batch_id} not found")

    # ------------------------------------------------------------------ M1: reads (tasks K1, K2)
    def list_batches(self, *, course_code: str | None = None, limit: int = 10,
                     offset: int = 0) -> list[dict]:
        """One page of batches, NEWEST FIRST (created_at descending), optionally of one course.

        Order of work: sort, then filter on course_code (when it is not None), then skip
        *offset* batches and keep at most *limit*. Return deep copies.
        """
        # TODO M1 (task K2): sorted(..., key=lambda b: b["created_at"], reverse=True); a list
        # comprehension for the filter; slicing [offset: offset + limit]; copy.deepcopy(...) the result.
        raise NotImplementedError("TODO M1: list_batches -- sort newest first, filter on course_code, slice offset/limit, return copies")

    def get_batch(self, batch_id: object) -> dict:
        """A copy of the batch with this id; NotFound otherwise."""
        # TODO M1 (task K2): one line -- a deep copy of what self._find_batch(batch_id) returns.
        raise NotImplementedError("TODO M1: get_batch -- a copy of the record self._find_batch returns")

    def list_scripts(self, batch_id: object, *, limit: int = 10, offset: int = 0) -> list[dict]:
        """One page of the scripts of a batch, ordered by candidate_number (ascending)."""
        # TODO M1 (task K2): find the batch, sort its "scripts" by candidate_number, slice, deep copy.
        raise NotImplementedError("TODO M1: list_scripts -- find the batch, sort its scripts by candidate_number, slice, copy")

    def custodian_of(self, batch_id: object) -> str:
        """The id of the current custodian of a batch (a plain string)."""
        # TODO M1 (task K2): the "current_custodian_id" entry of the record self._find_batch returns.
        raise NotImplementedError("TODO M1: custodian_of -- the current_custodian_id of the batch")

    def list_transfers(self, batch_id: object) -> list[dict]:
        """The custody history of a batch: all its transfers, OLDEST FIRST (requested_at ascending)."""
        # TODO M1 (task K2): find the batch, sort its "transfers" by requested_at, return deep copies.
        raise NotImplementedError("TODO M1: list_transfers -- the transfers of the batch, oldest first, copies")

    # ------------------------------------------------------------------ M2: create a batch (task F1)
    def create_batch(self, details: dict, created_by: str) -> dict:
        """Store a new batch made of the validated *details*; return a copy.

        *details* = {"course_code", "session_label", "candidate_numbers": [...]}.
        The store assigns: ``id`` (call self.new_id() FIRST), then one script per candidate number
        (self.new_id() once per script, in the order given), ``created_at`` (self.clock(), formatted
        with stamp()), ``script_count`` = number of candidates, ``created_by`` = *created_by* and
        ``current_custodian_id`` = *created_by* too (the officer holds the scripts at first),
        ``transfers`` = [].
        """
        # TODO M2 (task F1): build the dict (see the docstring and data/seed.json), append it to
        # self._batches, return copy.deepcopy(it). Careful: str(self.new_id()) -- ids are stored as text.
        # raise NotImplementedError("TODO M2: create_batch -- build the batch with its scripts, append, return a copy")
        
        id = str(self.new_id())
        new_batch = {
            "id": id,
            "course_code": details["course_code"],
            "session_label": details["session_label"],
            "script_count": len(details["candidate_numbers"]),
            "created_by": created_by,
            "current_custodian_id": created_by,
            "created_at": stamp(self.clock()),
            "transfers": [],
            "scripts": [
                {
                    "candidate_number":c,
                    "id":str(self.new_id()),
                    "batch_id":id
                    } for c in details["candidate_numbers"]
                ]
        }
        
        self._batches.append(new_batch)
        
        return copy.deepcopy(new_batch)
        

    # ------------------------------------------------------------------ M3: custody transfers (task F2)
    def request_transfer(self, batch_id: object, to_user_id: object, by_user: str) -> dict:
        """Start a handover of the batch from *by_user* to *to_user_id*; return a copy of the transfer.

        Rules, checked in this order:
          1. the batch must exist                                      -> NotFound
          2. *by_user* must be the current custodian                    -> Conflict
          3. the receiver must not be *by_user* himself                 -> Unprocessable
          4. the batch must have no transfer with status "pending"      -> Conflict
        Then append {"id": new_id, "batch_id", "from_user_id": by_user, "to_user_id", "status": "pending",
        "requested_at": stamp(self.clock())} to the batch's transfers. There is no responded_at yet.
        """
        # TODO M3 (task F2): follow the four rules above in that order, then build and append the transfer.
        # Check if the batch exist
        batch = self._find_batch(batch_id=batch_id)
        if batch is None:
            raise NotFound(message="The Batch is not found")
        
        # Check the current custodian
        if batch["current_custodian_id"] != by_user:
            raise Conflict(message="The user is not the owner of the batch")
        
        # Check if the current custodian is the to custodian
        if by_user == str(to_user_id):
            raise Unprocessable(message="You cannot be the receiver and the sender")
        
        # Create a list to hold pending transfers
        transfer_status_pending = [t for t in batch["transfers"] if t["status"] == "pending" ]
        
        # Check the length of the list if it contains atleast one pending transfer
        if len(transfer_status_pending) > 0:
            raise Conflict(message="The batch should not contain pending transfers")
        
        transfer = {
            "id": str(self.new_id()),
            "batch_id": batch["id"],
            "from_user_id": by_user,
            "to_user_id": str(to_user_id),
            "status": "pending",
            "requested_at": stamp(self.clock())
        }
        batch["transfers"].append(transfer)
        
        return copy.deepcopy(transfer)
        
        # raise NotImplementedError("TODO M3: request_transfer -- the four rules, then append a pending transfer")

    def accept_transfer(self, transfer_id: object, by_user: str) -> dict:
        """The receiver accepts a transfer: it becomes "accepted" and the receiver becomes custodian.

        Rules, in this order:
          1. a transfer with this id must exist (look in EVERY batch)        -> NotFound
          2. *by_user* must be the transfer's to_user_id                     -> Conflict
          3. the transfer must still be "pending"                            -> Conflict
        Then set status "accepted", responded_at = stamp(self.clock()), and update the batch's
        current_custodian_id in the SAME call (history stays append-only: the transfer is never deleted).
        Return a copy of the transfer.
        """
        # TODO M3 (task F2): two nested for-loops to find the transfer and remember its batch; then the three rules.
        
        # Get fisrt the transfer from a batch and remember its batch
        needed_transfer = None
        needed_batch = None 
        for batch in self._batches:
            for transfer in batch["transfers"]:
                if transfer["id"] == str(transfer_id):
                    needed_transfer = transfer
                    needed_batch = batch
        # Check the dict
        if needed_transfer is None:
            raise NotFound(message="Transfer not found")

        # Get the batch
        batch = self._find_batch(batch_id=needed_batch["id"])
    
        
        # Check the by_user if it matches the to_user_id of the transfer
        if by_user != str(needed_transfer["to_user_id"]):
            raise Conflict(message="This user is not supposed to have this transfer")
        
        # Check the transfer status if it is still pending
        if needed_transfer["status"] != "pending":
            raise Conflict(message="Every transfers needs to be pending")
        
        # Update the transfer status
        needed_transfer["status"] = "accepted"
        needed_transfer["responded_at"] = stamp(self.clock())
        
        # Update the current custodian
        batch["current_custodian_id"] = by_user
        
        return copy.deepcopy(needed_transfer)
        # raise NotImplementedError("TODO M3: accept_transfer -- find the transfer, three rules, accept it, move the custody")
