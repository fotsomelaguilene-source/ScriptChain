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
        # Find the batch first
        batch = self._find_batch(batch_id=batch_id)

        # Sort the marks by candidate number
        sorted_marks = sorted(batch["marks"], key=lambda m: m["candidate_number"])

        # Keep only the page we need
        page = sorted_marks[offset: offset + limit]

        return copy.deepcopy(page)

    def get_mark(self, mark_id: object) -> dict:
        """A copy of one mark; NotFound otherwise."""
        batch, mark = self._find_mark(mark_id=mark_id)

        return copy.deepcopy(mark)

    def list_adjustments(self, mark_id: object) -> list[dict]:
        """The change history of a mark, OLDEST FIRST (adjusted_at ascending), as copies."""
        batch, mark = self._find_mark(mark_id=mark_id)

        # Oldest adjustment first
        sorted_adjustments = sorted(mark["adjustments"], key=lambda a: a["adjusted_at"])

        return copy.deepcopy(sorted_adjustments)

    def pending(self) -> list[dict]:
        """The moderation queue: every mark batch that is NOT approved yet, newest first (created_at descending),
        as small dicts  {"batch_id": ..., "status": ..., "mark_count": <number of marks>}."""
        # Keep only the batches that are not approved
        not_approved = [b for b in self._batches if b["status"] != "approved"]

        # Newest first
        not_approved = sorted(not_approved, key=lambda b: b["created_at"], reverse=True)

        # Build the small dicts
        result = []
        for batch in not_approved:
            line = {
                "batch_id": batch["batch_id"],
                "status": batch["status"],
                "mark_count": len(batch["marks"])
            }
            result.append(line)

        return result

    def get_approval(self, batch_id: object) -> dict:
        """The approval record of a script batch (a copy). NotFound when the batch has no marks OR is not approved yet."""
        batch = self._find_batch(batch_id=batch_id)

        # No approval yet
        if batch["approval"] is None:
            raise NotFound(message=f"Batch {batch_id} is not approved")

        return copy.deepcopy(batch["approval"])

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
        # Read the clock only one time
        now = stamp(self.clock())

        # Try to get the mark batch, it may not exist yet
        try:
            batch = self._find_batch(batch_id=batch_id)
        except NotFound:
            batch = None

        if batch is not None:
            # Rule 1: an approved batch is locked
            if batch["status"] == "approved":
                raise Conflict(message="The marks of this batch are approved and locked")

            # Rule 2: a candidate cannot have two marks (check everything before saving anything)
            for entry in entries:
                for mark in batch["marks"]:
                    if mark["candidate_number"] == entry["candidate_number"]:
                        raise Conflict(message=f"The candidate {entry['candidate_number']} already has a mark")

        # Create the mark batch if it does not exist yet
        if batch is None:
            batch = {
                "id": str(self.new_id()),
                "batch_id": str(batch_id),
                "status": "entered",
                "created_at": now,
                "approval": None,
                "marks": []
            }
            self._batches.append(batch)

        # Create one mark for each entry, in the order given
        new_marks = []
        for entry in entries:
            mark = {
                "id": str(self.new_id()),
                "batch_id": batch["batch_id"],
                "candidate_number": entry["candidate_number"],
                "original_score": entry["score"],
                "current_score": entry["score"],
                "entered_by": by_user,
                "custodian_id_at_entry": custodian_id,
                "entered_at": now,
                "adjustments": []
            }
            batch["marks"].append(mark)
            new_marks.append(mark)

        return {
            "batch_id": batch["batch_id"],
            "status": batch["status"],
            "marks": copy.deepcopy(new_marks)
        }

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
        # Find the mark and its batch (NotFound if the mark does not exist)
        batch, mark = self._find_mark(mark_id=mark_id)

        # An approved batch is locked
        if batch["status"] == "approved":
            raise Conflict(message="The marks of this batch are approved and locked")

        # Create the adjustment, old_score is the CURRENT score of the mark
        adjustment = {
            "id": str(self.new_id()),
            "mark_id": mark["id"],
            "old_score": mark["current_score"],
            "new_score": new_score,
            "reason": reason,
            "adjusted_by": by_user,
            "adjusted_at": stamp(self.clock())
        }
        mark["adjustments"].append(adjustment)

        # Change the current score (the original score never changes)
        mark["current_score"] = new_score

        # The first adjustment moves the batch to in_moderation
        if batch["status"] == "entered":
            batch["status"] = "in_moderation"

        return copy.deepcopy(adjustment)

    def approve(self, batch_id: object, by_user: str) -> dict:
        """The head of department approves a batch: its marks are locked for ever. Returns a copy of the approval.

        Rules: the batch must have marks (NotFound otherwise, self._find_batch does it); it must not be approved
        already (Conflict). Then set status "approved" and approval = {"id": self.new_id(), "batch_id", "approved_by":
        by_user, "approved_at": stamp(self.clock())}.
        """
        # Find the batch (NotFound if it has no marks)
        batch = self._find_batch(batch_id=batch_id)

        # It cannot be approved two times
        if batch["status"] == "approved":
            raise Conflict(message="This batch is already approved")

        # Create the approval record
        approval = {
            "id": str(self.new_id()),
            "batch_id": batch["batch_id"],
            "approved_by": by_user,
            "approved_at": stamp(self.clock())
        }

        # Save it and lock the batch
        batch["status"] = "approved"
        batch["approval"] = approval

        return copy.deepcopy(approval)
