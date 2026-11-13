"""M1 -- the read operations: marks of a batch, one mark, its adjustments, the moderation queue, the approval.

These tests use the SEED mark batches only (data/seed.json), so they do not need M2 or M3.
Seed: CSC201 = "entered" (3 marks), MTH101 = "approved" (2 marks, one adjusted), NET301 = "in_moderation" (2 marks).
"""
import pytest

from tests.conftest import (ADJUSTMENT_KEYS, BATCH_CSC201, BATCH_MTH101, BATCH_NET301, HOD, HOD_ID, MARK_CN1001,
                            MARK_CN2001, MARK_KEYS, MODERATOR, MODERATOR_ID, OFFICER, UNKNOWN_BATCH, UNKNOWN_MARK)

pytestmark = pytest.mark.m1


# ---- marks of a batch -----------------------------------------------------------------------
def test_marks_of_a_batch_are_ordered_by_candidate_number(api):
    response = api.get("/v1/batches/{batch_id}/marks", as_=OFFICER, batch_id=BATCH_CSC201)
    assert response.status_code == 200
    marks = response.json()["marks"]
    assert [m["candidate_number"] for m in marks] == ["CN1001", "CN1002", "CN1003"]
    assert [m["current_score"] for m in marks] == [62.5, 48, 91]


def test_marks_limit_and_offset(api):
    page = api.get("/v1/batches/{batch_id}/marks", as_=OFFICER, batch_id=BATCH_CSC201, params={"limit": 1, "offset": 1})
    assert [m["candidate_number"] for m in page.json()["marks"]] == ["CN1002"]
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        response = api.get("/v1/batches/{batch_id}/marks", as_=OFFICER, batch_id=BATCH_CSC201, params=params)
        assert response.status_code == 422, params
        assert response.json()["detail"][0]["loc"] == ["query", next(iter(params))]


def test_marks_are_shown_without_their_internal_adjustment_list(api):
    """The stored mark holds a list 'adjustments'; the spec's MarkSchema does not show it."""
    for batch in (BATCH_CSC201, BATCH_MTH101, BATCH_NET301):
        for mark in api.get("/v1/batches/{batch_id}/marks", as_=OFFICER, batch_id=batch).json()["marks"]:
            assert set(mark) == MARK_KEYS, mark["id"]


def test_a_batch_without_marks_is_404(api):
    response = api.get("/v1/batches/{batch_id}/marks", as_=OFFICER, batch_id=UNKNOWN_BATCH)
    assert response.status_code == 404
    assert UNKNOWN_BATCH in response.json()["detail"]


# ---- one mark -------------------------------------------------------------------------------
def test_get_mark_shows_the_original_and_the_current_score(api):
    response = api.get("/v1/marks/{mark_id}", as_=OFFICER, mark_id=MARK_CN2001)
    assert response.status_code == 200
    mark = response.json()
    assert (mark["candidate_number"], mark["original_score"], mark["current_score"]) == ("CN2001", 65, 70)
    assert mark["batch_id"] == BATCH_MTH101
    assert mark["entered_at"] == "2026-10-21T12:00:00Z"


def test_unknown_mark_is_404_and_malformed_id_is_422(api):
    response = api.get("/v1/marks/{mark_id}", as_=OFFICER, mark_id=UNKNOWN_MARK)
    assert response.status_code == 404
    assert response.json() == {"detail": f"Mark {UNKNOWN_MARK} not found"}
    response = api.get("/v1/marks/{mark_id}", as_=OFFICER, mark_id="nope")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "mark_id"]


# ---- adjustments ----------------------------------------------------------------------------
def test_change_history_of_a_mark(api):
    history = api.get("/v1/marks/{mark_id}/adjustments", as_=OFFICER, mark_id=MARK_CN2001).json()["adjustments"]
    assert len(history) == 1
    adjustment = history[0]
    assert set(adjustment) == ADJUSTMENT_KEYS
    assert (adjustment["old_score"], adjustment["new_score"]) == (65, 70)
    assert adjustment["reason"] == "Question 4 was marked twice by mistake"
    assert adjustment["adjusted_by"] == MODERATOR_ID
    assert api.get("/v1/marks/{mark_id}/adjustments", as_=OFFICER, mark_id=MARK_CN1001).json() == {"adjustments": []}
    assert api.get("/v1/marks/{mark_id}/adjustments", as_=OFFICER, mark_id=UNKNOWN_MARK).status_code == 404


# ---- moderation queue -----------------------------------------------------------------------
def test_pending_lists_the_batches_that_are_not_approved_newest_first(api):
    response = api.get("/v1/moderation/pending", as_=MODERATOR)
    assert response.status_code == 200
    assert response.json() == {"batches": [
        {"batch_id": BATCH_NET301, "status": "in_moderation", "mark_count": 2},
        {"batch_id": BATCH_CSC201, "status": "entered", "mark_count": 3},
    ]}
    assert api.get("/v1/moderation/pending", as_=HOD).status_code == 200


# ---- approval record ------------------------------------------------------------------------
def test_get_approval(api):
    response = api.get("/v1/batches/{batch_id}/approval", as_=OFFICER, batch_id=BATCH_MTH101)
    assert response.status_code == 200
    approval = response.json()
    assert approval["batch_id"] == BATCH_MTH101
    assert approval["approved_by"] == HOD_ID
    assert approval["approved_at"] == "2026-10-23T15:00:00Z"


def test_a_batch_that_is_not_approved_has_no_approval_record(api):
    assert api.get("/v1/batches/{batch_id}/approval", as_=OFFICER, batch_id=BATCH_CSC201).status_code == 404
    assert api.get("/v1/batches/{batch_id}/approval", as_=OFFICER, batch_id=UNKNOWN_BATCH).status_code == 404
