"""Unit tests: the schemas and the store, WITHOUT HTTP.

They give you feedback on one piece at a time, before the routes exist:
  K1 -> response models   K2 -> store reads   F3 -> bulk request models + submit_marks   F4 -> adjust and approve
"""
import copy
import json

import pytest
from pydantic import ValidationError

from app.errors import Conflict, NotFound
from app.schemas import (AdjustmentRequestSchema, AdjustmentSchema, ApprovalSchema, BulkMarksSchema, MarkEntrySchema,
                         MarkSchema, MarksSchema, PendingSchema)
from app.store import SEED_PATH
from tests.conftest import (ADJUSTMENT_KEYS, BATCH_CSC201, BATCH_MTH101, BATCH_NET301, BATCH_NEW, EXAMINER_1_ID,
                            FROZEN_CREATED, HOD_ID, MARK_CN1001, MARK_CN2001, MARK_KEYS, MODERATOR_ID, NEW_IDS,
                            UNKNOWN_BATCH, UNKNOWN_MARK, bulk, make_store)

SEED = json.loads(SEED_PATH.read_text(encoding="utf-8"))
CSC201, MTH101 = SEED[0], SEED[1]


def shown(model, data):
    return model.model_validate(data).model_dump(mode="json", exclude_none=True)


# =============================================================================== K1: response models
@pytest.mark.m1
def test_mark_schema_hides_the_adjustment_list():
    assert set(shown(MarkSchema, MTH101["marks"][0])) == MARK_KEYS
    assert set(shown(MarksSchema, {"marks": CSC201["marks"]})["marks"][0]) == MARK_KEYS


@pytest.mark.m1
def test_adjustment_approval_and_pending_schemas():
    adjustment = MTH101["marks"][0]["adjustments"][0]
    assert set(shown(AdjustmentSchema, adjustment)) == ADJUSTMENT_KEYS
    assert set(shown(ApprovalSchema, MTH101["approval"])) == {"id", "batch_id", "approved_by", "approved_at"}
    line = {"batch_id": BATCH_CSC201, "status": "entered", "mark_count": 3}
    assert shown(PendingSchema, {"batches": [line]}) == {"batches": [line]}


@pytest.mark.m1
def test_response_models_check_the_types():
    broken = copy.deepcopy(MTH101["marks"][0])
    broken["current_score"] = "high"
    with pytest.raises(ValidationError):
        MarkSchema.model_validate(broken)
    with pytest.raises(ValidationError):
        PendingSchema.model_validate({"batches": [{"batch_id": BATCH_CSC201, "status": "unknown", "mark_count": 3}]})


# =============================================================================== K2: store reads
@pytest.mark.m1
def test_store_marks_are_sorted_sliced_and_copied():
    store = make_store()
    assert [m["candidate_number"] for m in store.list_marks(BATCH_CSC201)] == ["CN1001", "CN1002", "CN1003"]
    assert [m["candidate_number"] for m in store.list_marks(BATCH_CSC201, limit=1, offset=2)] == ["CN1003"]
    store.list_marks(BATCH_CSC201)[0]["current_score"] = 0
    store.get_mark(MARK_CN1001)["current_score"] = 0
    assert store.get_mark(MARK_CN1001)["current_score"] == 62.5          # copies, not the stored records
    with pytest.raises(NotFound):
        store.list_marks(UNKNOWN_BATCH)
    with pytest.raises(NotFound):
        store.get_mark(UNKNOWN_MARK)


@pytest.mark.m1
def test_store_adjustments_pending_and_approval():
    store = make_store()
    assert [a["new_score"] for a in store.list_adjustments(MARK_CN2001)] == [70]
    assert store.list_adjustments(MARK_CN1001) == []
    with pytest.raises(NotFound):
        store.list_adjustments(UNKNOWN_MARK)
    assert store.pending() == [{"batch_id": BATCH_NET301, "status": "in_moderation", "mark_count": 2},
                               {"batch_id": BATCH_CSC201, "status": "entered", "mark_count": 3}]
    assert store.get_approval(BATCH_MTH101)["approved_by"] == HOD_ID
    for batch in (BATCH_CSC201, UNKNOWN_BATCH):
        with pytest.raises(NotFound):
            store.get_approval(batch)


# =============================================================================== F3: bulk submission
@pytest.mark.m2
def test_bulk_schema_accepts_valid_marks():
    payload = bulk(("CN0001", 50), ("CN0002", 61.5), ("CN0003", 0), ("CN0004", 100))
    assert BulkMarksSchema.model_validate(payload).model_dump(mode="json")["entries"][1]["score"] == 61.5


@pytest.mark.m2
@pytest.mark.parametrize("payload", [
    bulk(("CN0001", -1)), bulk(("CN0001", 100.5)), bulk(("CN0001", "50")), bulk(("CN0001", True)),
    bulk(("CN12", 50)), bulk(("CN0001", 50), ("CN0001", 60)), {"entries": []}, {},
    {"entries": [{"candidate_number": "CN0001"}]},
])
def test_bulk_schema_refuses_invalid_marks(payload):
    with pytest.raises(ValidationError):
        BulkMarksSchema.model_validate(payload)


@pytest.mark.m2
def test_mark_entry_schema():
    assert MarkEntrySchema.model_validate({"candidate_number": "CN0001", "score": 12}).score == 12
    with pytest.raises(ValidationError):
        MarkEntrySchema.model_validate({"candidate_number": "CN0001", "score": 101})


@pytest.mark.m2
def test_store_submit_marks_creates_the_batch_and_the_marks():
    store = make_store()
    entries = bulk(("CN0002", 50), ("CN0001", 61.5))["entries"]
    result = store.submit_marks(BATCH_NEW, entries, EXAMINER_1_ID, EXAMINER_1_ID)
    assert (result["batch_id"], result["status"]) == (BATCH_NEW, "entered")
    first = result["marks"][0]
    assert first["id"] == NEW_IDS[1]                                  # NEW_IDS[0] went to the mark BATCH
    assert [m["id"] for m in result["marks"]] == [NEW_IDS[1], NEW_IDS[2]]
    assert (first["original_score"], first["current_score"], first["entered_at"]) == (50, 50, FROZEN_CREATED)
    assert (first["entered_by"], first["custodian_id_at_entry"]) == (EXAMINER_1_ID, EXAMINER_1_ID)
    assert [m["candidate_number"] for m in store._find_batch(BATCH_NEW)["marks"]] == ["CN0002", "CN0001"]   # insertion order
    # a second submission for the same batch does NOT create a second mark batch (so no id is spent on it)
    more = store.submit_marks(BATCH_NEW, bulk(("CN0003", 70))["entries"], EXAMINER_1_ID, EXAMINER_1_ID)
    assert more["marks"][0]["id"] == NEW_IDS[3]


@pytest.mark.m2
def test_store_submit_marks_rules():
    store = make_store()
    with pytest.raises(Conflict):                                      # approved = locked
        store.submit_marks(BATCH_MTH101, bulk(("CN2009", 50))["entries"], EXAMINER_1_ID, EXAMINER_1_ID)
    store.submit_marks(BATCH_NEW, bulk(("CN0001", 50))["entries"], EXAMINER_1_ID, EXAMINER_1_ID)
    with pytest.raises(Conflict):                                      # never overwritten, and nothing partial
        store.submit_marks(BATCH_NEW, bulk(("CN0001", 99), ("CN0002", 40))["entries"], EXAMINER_1_ID, EXAMINER_1_ID)
    assert [(m["candidate_number"], m["current_score"]) for m in store._find_batch(BATCH_NEW)["marks"]] == [("CN0001", 50)]


# =============================================================================== F4: adjust and approve
@pytest.mark.m3
def test_adjustment_request_schema():
    ok = AdjustmentRequestSchema.model_validate({"new_score": 65, "reason": "  typo  "})
    assert (ok.new_score, ok.reason) == (65, "typo")                   # spaces around the reason are stripped
    for bad in ({"new_score": 65, "reason": ""}, {"new_score": 65, "reason": "   "}, {"new_score": 65},
                {"new_score": 101, "reason": "x"}, {"new_score": "65", "reason": "x"},
                {"new_score": 65, "reason": "x" * 501}):
        with pytest.raises(ValidationError):
            AdjustmentRequestSchema.model_validate(bad)


@pytest.mark.m3
def test_store_add_adjustment():
    store = make_store()
    adjustment = store.add_adjustment(MARK_CN1001, 65, "Addition error", MODERATOR_ID)
    assert adjustment == {"id": NEW_IDS[0], "mark_id": MARK_CN1001, "old_score": 62.5, "new_score": 65,
                          "reason": "Addition error", "adjusted_by": MODERATOR_ID, "adjusted_at": FROZEN_CREATED}
    _batch, mark = store._find_mark(MARK_CN1001)
    assert (mark["original_score"], mark["current_score"]) == (62.5, 65)
    assert store._find_batch(BATCH_CSC201)["status"] == "in_moderation"
    second = store.add_adjustment(MARK_CN1001, 70, "again", MODERATOR_ID)
    assert second["old_score"] == 65                                   # remembers the score just before
    with pytest.raises(NotFound):
        store.add_adjustment(UNKNOWN_MARK, 50, "x", MODERATOR_ID)
    with pytest.raises(Conflict):                                      # MTH101 is approved
        store.add_adjustment(MARK_CN2001, 10, "late", MODERATOR_ID)
    assert store._find_mark(MARK_CN2001)[1]["current_score"] == 70


@pytest.mark.m3
def test_store_approve():
    store = make_store()
    approval = store.approve(BATCH_NET301, HOD_ID)
    assert approval == {"id": NEW_IDS[0], "batch_id": BATCH_NET301, "approved_by": HOD_ID,
                        "approved_at": FROZEN_CREATED}
    assert store._find_batch(BATCH_NET301)["approval"] == approval
    assert store._find_batch(BATCH_NET301)["status"] == "approved"
    with pytest.raises(Conflict):
        store.approve(BATCH_NET301, HOD_ID)                            # twice
    with pytest.raises(Conflict):
        store.approve(BATCH_MTH101, HOD_ID)                            # approved in the seed
    with pytest.raises(NotFound):
        store.approve(UNKNOWN_BATCH, HOD_ID)
    with pytest.raises(Conflict):                                      # locked for good
        store.add_adjustment(store._find_batch(BATCH_NET301)["marks"][0]["id"], 1, "late", MODERATOR_ID)
