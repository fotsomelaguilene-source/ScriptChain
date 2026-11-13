"""M3 -- moderation (adjustments with a reason) and approval (which LOCKS the marks)."""
import pytest

from tests.conftest import (ADJUSTMENT_KEYS, BATCH_CSC201, BATCH_MTH101, BATCH_NET301, EXAMINER_ONE, FIRST_NEW_ID,
                            FROZEN_CREATED, HOD, HOD_ID, MARK_CN1001, MARK_CN2001, MODERATOR, MODERATOR_ID, OFFICER,
                            UNKNOWN_BATCH, UNKNOWN_MARK, bulk, key)

pytestmark = pytest.mark.m3

ADJ = "/v1/marks/{mark_id}/adjustments"
APPROVAL = "/v1/batches/{batch_id}/approval"


def mark(api, mark_id):
    return api.get("/v1/marks/{mark_id}", as_=OFFICER, mark_id=mark_id).json()


def pending(api):
    return {b["batch_id"]: b["status"] for b in api.get("/v1/moderation/pending", as_=MODERATOR).json()["batches"]}


# ---- adjustments ----------------------------------------------------------------------------
def test_a_moderator_adjusts_a_mark_with_a_reason(api):
    response = api.post(ADJ, as_=MODERATOR, mark_id=MARK_CN1001, json={"new_score": 65, "reason": "Addition error"})
    assert response.status_code == 201
    adjustment = response.json()
    assert set(adjustment) == ADJUSTMENT_KEYS
    assert adjustment["id"] == FIRST_NEW_ID
    assert (adjustment["old_score"], adjustment["new_score"]) == (62.5, 65)
    assert adjustment["reason"] == "Addition error"
    assert adjustment["adjusted_by"] == MODERATOR_ID
    assert adjustment["adjusted_at"] == FROZEN_CREATED
    current = mark(api, MARK_CN1001)
    assert (current["original_score"], current["current_score"]) == (62.5, 65)     # the original is never overwritten


def test_adjustments_pile_up_and_each_remembers_the_score_before_it(api):
    api.post(ADJ, as_=MODERATOR, mark_id=MARK_CN1001, json={"new_score": 65, "reason": "first"})
    api.post(ADJ, as_=MODERATOR, mark_id=MARK_CN1001, json={"new_score": 70, "reason": "second"})
    history = api.get(ADJ, as_=OFFICER, mark_id=MARK_CN1001).json()["adjustments"]
    assert [(a["old_score"], a["new_score"], a["reason"]) for a in history] == [(62.5, 65, "first"), (65, 70, "second")]


def test_the_first_adjustment_moves_the_batch_to_in_moderation(api):
    assert pending(api)[BATCH_CSC201] == "entered"
    api.post(ADJ, as_=MODERATOR, mark_id=MARK_CN1001, json={"new_score": 65, "reason": "x"})
    assert pending(api)[BATCH_CSC201] == "in_moderation"


@pytest.mark.parametrize("payload, loc", [
    ({"new_score": 65, "reason": ""}, ["body", "reason"]),
    ({"new_score": 65, "reason": "     "}, ["body", "reason"]),
    ({"new_score": 65}, ["body", "reason"]),
    ({"new_score": 101, "reason": "x"}, ["body", "new_score"]),
    ({"new_score": "65", "reason": "x"}, ["body", "new_score"]),
    ({"new_score": 65, "reason": "x" * 501}, ["body", "reason"]),
])
def test_an_adjustment_needs_a_valid_score_and_a_real_reason(api, payload, loc):
    response = api.post(ADJ, as_=MODERATOR, mark_id=MARK_CN1001, json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == loc
    assert mark(api, MARK_CN1001)["current_score"] == 62.5
    assert api.get(ADJ, as_=OFFICER, mark_id=MARK_CN1001).json() == {"adjustments": []}


def test_adjust_an_unknown_mark_is_404(api):
    assert api.post(ADJ, as_=MODERATOR, mark_id=UNKNOWN_MARK, json={"new_score": 65, "reason": "x"}).status_code == 404


def test_approved_marks_cannot_be_adjusted(api):
    response = api.post(ADJ, as_=MODERATOR, mark_id=MARK_CN2001, json={"new_score": 10, "reason": "too late"})
    assert response.status_code == 409
    assert mark(api, MARK_CN2001)["current_score"] == 70
    assert len(api.get(ADJ, as_=OFFICER, mark_id=MARK_CN2001).json()["adjustments"]) == 1


# ---- approval -------------------------------------------------------------------------------
def test_the_hod_approves_a_batch(api):
    response = api.post(APPROVAL, as_=HOD, batch_id=BATCH_NET301)
    assert response.status_code == 201
    approval = response.json()
    assert approval["id"] == FIRST_NEW_ID
    assert approval["batch_id"] == BATCH_NET301
    assert approval["approved_by"] == HOD_ID
    assert approval["approved_at"] == FROZEN_CREATED
    assert api.get(APPROVAL, as_=OFFICER, batch_id=BATCH_NET301).json() == approval
    assert BATCH_NET301 not in pending(api)                               # it left the moderation queue


def test_approval_locks_the_marks(api, custodians):
    api.post(APPROVAL, as_=HOD, batch_id=BATCH_CSC201)
    # no adjustment any more ...
    locked = api.post(ADJ, as_=MODERATOR, mark_id=MARK_CN1001, json={"new_score": 65, "reason": "late"})
    assert locked.status_code == 409
    # ... and no new marks either, even from the custodian (examiner 1 holds CSC201 in the fake)
    more = api.post("/v1/batches/{batch_id}/marks/bulk", as_=EXAMINER_ONE, batch_id=BATCH_CSC201,
                    headers=key(), json=bulk(("CN1009", 50)))
    assert more.status_code == 409


def test_a_batch_cannot_be_approved_twice(api):
    assert api.post(APPROVAL, as_=HOD, batch_id=BATCH_MTH101).status_code == 409     # approved in the seed
    api.post(APPROVAL, as_=HOD, batch_id=BATCH_CSC201)
    assert api.post(APPROVAL, as_=HOD, batch_id=BATCH_CSC201).status_code == 409


def test_a_batch_without_marks_cannot_be_approved(api):
    assert api.post(APPROVAL, as_=HOD, batch_id=UNKNOWN_BATCH).status_code == 404
    assert api.post(APPROVAL, as_=HOD, batch_id="nope").status_code == 422


# ---- the whole story ------------------------------------------------------------------------
def test_full_marking_workflow(api):
    new_batch = "ab8e1eb0-195b-51a8-95b7-17b938ba6604"                      # BATCH_NEW: examiner 1 is its custodian
    entered = api.post("/v1/batches/{batch_id}/marks/bulk", as_=EXAMINER_ONE, batch_id=new_batch,
                       headers=key(), json=bulk(("CN0001", 40), ("CN0002", 80))).json()
    assert entered["status"] == "entered"
    target = entered["marks"][0]["id"]
    api.post(ADJ, as_=MODERATOR, mark_id=target, json={"new_score": 45, "reason": "Second marker found a missed answer"})
    assert pending(api)[new_batch] == "in_moderation"
    api.post(APPROVAL, as_=HOD, batch_id=new_batch)
    assert new_batch not in pending(api)
    final = mark(api, target)
    assert (final["original_score"], final["current_score"]) == (40, 45)
