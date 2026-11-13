"""The in-memory store of the Mark service: the only place where its data lives.

The marks of one script batch are kept together in a "mark batch" (the aggregate of the class diagram):

    {"id": "...", "batch_id": "<id of the batch in the SCRIPT service>", "status": "entered" | "in_moderation" | "approved",
     "created_at": "2026-10-20T10:00:00Z", "approval": None or {"id", "batch_id", "approved_by", "approved_at"},
     "marks": [{"id", "batch_id", "candidate_number", "original_score", "current_score", "entered_by",
                "custodian_id_at_entry", "entered_at",
                "adjustments": [{"id", "mark_id", "old_score", "new_score", "reason", "adjusted_by", "adjusted_at"}]}]}

Same rules of the house as the Script store: ids are text, timestamps are text ("...Z"), the store hands out
DEEP COPIES, it raises errors from app/errors.py, nothing is kept when the process stops.
Marks are NEVER overwritten: original_score stays as entered; an adjustment adds a row and moves current_score.
batch_id is a plain value pointing into ANOTHER service's data: there is no foreign key between databases.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.clock import new_uuid, stamp, utc_now
from app.errors import Conflict, NotFound

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed.json"


class MarkStore:
    """A list of mark batches with the operations the API needs."""

    def __init__(self, mark_batches: Iterable[dict] = (), *,
                 clock: Callable[[], datetime] = utc_now,
                 new_id: Callable[[], UUID] = new_uuid) -> None:
        self._batches: list[dict] = [copy.deepcopy(batch) for batch in mark_batches]
        self._idempotency: dict[str, dict] = {}
        self.clock = clock
        self.new_id = new_id

    @classmethod
    def from_seed(cls, path: Path = SEED_PATH, **kwargs) -> MarkStore:
        with path.open(encoding="utf-8") as fh:
            return cls(json.load(fh), **kwargs)

    # ------------------------------------------------------------------ PROVIDED helpers (worked examples)
    def _find_batch(self, batch_id: object) -> dict:
        """The stored mark batch (NOT a copy) of a script batch; NotFound when no marks were ever submitted."""
        for batch in self._batches:
            if batch["batch_id"] == str(batch_id):
                return batch
        raise NotFound(f"No marks were submitted for batch {batch_id}")

    def _find_mark(self, mark_id: object) -> tuple[dict, dict]:
        """(the stored mark batch, the stored mark) of a mark id; NotFound otherwise. Look in EVERY batch."""
        for batch in self._batches:
            for mark in batch["marks"]:
                if mark["id"] == str(mark_id):
                    return batch, mark
        raise NotFound(f"Mark {mark_id} not found")

    def find_idempotent(self, key: str) -> dict | None:
        """What was remembered for this Idempotency-Key: {"fingerprint", "response"}, or None."""
        found = self._idempotency.get(key)
        return copy.deepcopy(found) if found else None

    def remember(self, key: str, fingerprint: str, response: dict) -> None:
        """Remember the answer given to a request, so that a retry with the same key gets the same answer."""
        self._idempotency[key] = {"fingerprint": fingerprint, "response": copy.deepcopy(response)}

    # ------------------------------------------------------------------ M1: reads (tasks K1, K2)
    def list_marks(self, batch_id: object, *, limit: int = 10, offset: int = 0) -> list[dict]:
        """One page of the marks of a script batch, ordered by candidate_number (ascending). NotFound when
        no marks were submitted for that batch (self._find_batch raises it for you)."""
        # TODO M1 (task K2): find the batch, sort its "marks" by candidate_number, slice [offset: offset + limit], deep copy.
        raise NotImplementedError("TODO M1: list_marks -- find the batch, sort its marks by candidate_number, slice, copy")

    def get_mark(self, mark_id: object) -> dict:
        """A copy of one mark; NotFound otherwise."""
        # TODO M1 (task K2): self._find_mark returns TWO things: `batch, mark = self._find_mark(mark_id)`. Return a copy of the mark.
        raise NotImplementedError("TODO M1: get_mark -- a copy of the mark self._find_mark returns")

    def list_adjustments(self, mark_id: object) -> list[dict]:
        """The change history of a mark, OLDEST FIRST (adjusted_at ascending), as copies."""
        # TODO M1 (task K2): find the mark, sort mark["adjustments"] by adjusted_at, deep copy.
        raise NotImplementedError("TODO M1: list_adjustments -- the adjustments of the mark, oldest first, copies")

    def pending(self) -> list[dict]:
        """The moderation queue: every mark batch that is NOT approved yet, newest first (created_at descending),
        as small dicts  {"batch_id": ..., "status": ..., "mark_count": <number of marks>}."""
        # TODO M1 (task K2): filter the batches whose status is not "approved", sort by created_at (newest first),
        # build one small dict per batch. len(batch["marks"]) gives the mark_count.
        raise NotImplementedError("TODO M1: pending -- the not-yet-approved batches as {batch_id, status, mark_count}, newest first")

    def get_approval(self, batch_id: object) -> dict:
        """The approval record of a script batch (a copy). NotFound when the batch has no marks OR is not approved yet."""
        # TODO M1 (task K2): find the batch (it may raise NotFound); if its "approval" is None raise
        # NotFound(f"Batch {batch_id} is not approved"); otherwise return a copy of the approval.
        raise NotImplementedError("TODO M1: get_approval -- the approval of the batch, NotFound when there is none")

    # ------------------------------------------------------------------ M2: bulk submission (task F3)
    def submit_marks(self, batch_id: object, entries: list[dict], by_user: str, custodian_id: str) -> dict:
        """Save the marks of *entries* ([{"candidate_number", "score"}, ...]) for a script batch.

        Returns {"batch_id": ..., "status": <status of the mark batch>, "marks": [copies of the NEW marks]}.
        Rules, in this order:
          1. if a mark batch exists for batch_id and its status is "approved"        -> Conflict (locked)
          2. if one of the candidates already has a mark in that batch                -> Conflict (never overwritten:
             a correction goes through an adjustment)
        Then: if no mark batch exists yet, create it (id = self.new_id() -- called ONLY when it is created,
        status "entered", created_at = the timestamp below, approval None, marks []). For each entry, in the order
        given, create a mark (id = self.new_id()) with original_score = current_score = the score, entered_by = by_user,
        custodian_id_at_entry = custodian_id, entered_at = the timestamp below, adjustments [].
        TIMESTAMP: call self.clock() ONCE at the start (stamp(...)) and use it for created_at and every entered_at.
        """
        # TODO M2 (task F3): follow the docstring. Useful: a set of the candidate numbers already entered
        # ({m["candidate_number"] for m in batch["marks"]}), and `try: batch = self._find_batch(batch_id) except NotFound: batch = None`.
        raise NotImplementedError("TODO M2: submit_marks -- locked? duplicates? create the mark batch and the marks")

    # ------------------------------------------------------------------ M3: moderation and approval (task F4)
    def add_adjustment(self, mark_id: object, new_score: float, reason: str, by_user: str) -> dict:
        """A moderator changes a mark. Returns a copy of the new adjustment.

        Rules, in this order:
          1. the mark must exist                                   -> NotFound (self._find_mark does it)
          2. the mark's batch must not be "approved"               -> Conflict (approved marks are locked)
        Then append {"id": self.new_id(), "mark_id", "old_score": the mark's CURRENT score, "new_score", "reason",
        "adjusted_by": by_user, "adjusted_at": stamp(self.clock())} to the mark's adjustments, set the mark's
        current_score to new_score (original_score never changes), and if the batch status was "entered" make it
        "in_moderation".
        """
        # TODO M3 (task F4): `batch, mark = self._find_mark(mark_id)`, then the rule, then the changes.
        raise NotImplementedError("TODO M3: add_adjustment -- locked? record the adjustment, move current_score, update the status")

    def approve(self, batch_id: object, by_user: str) -> dict:
        """The head of department approves a batch: its marks are locked for ever. Returns a copy of the approval.

        Rules: the batch must have marks (NotFound otherwise, self._find_batch does it); it must not be approved
        already (Conflict). Then set status "approved" and approval = {"id": self.new_id(), "batch_id", "approved_by":
        by_user, "approved_at": stamp(self.clock())}.
        """
        # TODO M3 (task F4): find the batch, check it is not already approved, then set the status and the approval.
        raise NotImplementedError("TODO M3: approve -- not already approved? set status 'approved' and the approval record")
