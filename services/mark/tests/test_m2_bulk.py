"""M2 -- POST /v1/batches/{batch_id}/marks/bulk: custodian check, fail closed, idempotency, locking.

Business rule of the brief: ONLY THE CURRENT CUSTODIAN can enter marks (409 otherwise).
"""
import jwt
import pytest

from tests.conftest import (BATCH_MTH101, BATCH_NEW, BATCH_NET301, EXAMINER_1_ID, EXAMINER_ONE, EXAMINER_TWO,
                            FIRST_NEW_ID, FROZEN_CREATED, MARK_KEYS, NEW_IDS, OFFICER, UNKNOWN_BATCH, bulk, key)

pytestmark = pytest.mark.m2

URL = "/v1/batches/{batch_id}/marks/bulk"


def marks_of(api, batch_id):
    return api.get("/v1/batches/{batch_id}/marks", as_=OFFICER, batch_id=batch_id, params={"limit": 100})


def test_the_custodian_saves_marks(api, custodians):
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key(),
                        json=bulk(("CN0002", 50), ("CN0001", 61.5)))
    assert response.status_code == 201
    result = response.json()
    assert (result["batch_id"], result["status"]) == (BATCH_NEW, "entered")
    assert [m["candidate_number"] for m in result["marks"]] == ["CN0002", "CN0001"]       # the order given
    first = result["marks"][0]
    assert set(first) == MARK_KEYS
    assert (first["original_score"], first["current_score"]) == (50, 50)
    assert first["entered_by"] == EXAMINER_1_ID
    assert first["custodian_id_at_entry"] == EXAMINER_1_ID                   # the audit snapshot
    assert first["entered_at"] == FROZEN_CREATED
    # ids: the mark batch took NEW_IDS[0] (only when created), then one id per mark, in order
    assert [m["id"] for m in result["marks"]] == [NEW_IDS[1], NEW_IDS[2]]
    stored = marks_of(api, BATCH_NEW).json()["marks"]
    assert [m["candidate_number"] for m in stored] == ["CN0001", "CN0002"]   # sorted by the API


def test_the_caller_token_is_forwarded_to_the_script_service(api, custodians):
    api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key(), json=bulk(("CN0001", 50)))
    assert len(custodians.calls) == 1
    batch_id, token = custodians.calls[0]
    assert batch_id == BATCH_NEW
    assert jwt.decode(token, options={"verify_signature": False})["sub"] == EXAMINER_1_ID


def test_only_the_current_custodian_can_enter_marks(api):
    # examiner 2 is an examiner but the Script service says examiner 1 holds the batch
    response = api.post(URL, as_=EXAMINER_TWO, batch_id=BATCH_NEW, headers=key(), json=bulk(("CN0001", 50)))
    assert response.status_code == 409
    assert marks_of(api, BATCH_NEW).status_code == 404            # nothing was saved


def test_when_the_script_service_is_down_marks_are_refused_with_503(api, custodians):
    custodians.down = True
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key(), json=bulk(("CN0001", 50)))
    assert response.status_code == 503                            # fail closed: unverified marks are never accepted
    custodians.down = False
    assert marks_of(api, BATCH_NEW).status_code == 404


def test_a_batch_unknown_to_the_script_service_is_404(api):
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=UNKNOWN_BATCH, headers=key(), json=bulk(("CN0001", 50)))
    assert response.status_code == 404


def test_the_idempotency_key_header_is_required(api):
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, json=bulk(("CN0001", 50)))
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["header", "idempotency-key"]


@pytest.mark.parametrize("payload, loc", [
    (bulk(("CN0001", -1)), ["body", "entries", 0, "score"]),
    (bulk(("CN0001", 100.5)), ["body", "entries", 0, "score"]),
    (bulk(("CN0001", "50")), ["body", "entries", 0, "score"]),
    (bulk(("CN0001", True)), ["body", "entries", 0, "score"]),
    (bulk(("CN12", 50)), ["body", "entries", 0, "candidate_number"]),
    (bulk(("CN0001", 50), ("CN0001", 60)), ["body", "entries"]),
    ({"entries": []}, ["body", "entries"]),
    ({"entries": [{"candidate_number": "CN0001"}]}, ["body", "entries", 0, "score"]),
    ({}, ["body", "entries"]),
])
def test_invalid_marks_are_rejected_with_422_and_nothing_is_saved(api, payload, loc):
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key(), json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == loc
    assert marks_of(api, BATCH_NEW).status_code == 404


def test_a_retry_with_the_same_key_does_not_save_twice(api, custodians):
    first = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("retry-key-1"), json=bulk(("CN0001", 50)))
    again = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("retry-key-1"), json=bulk(("CN0001", 50)))
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()                           # the FIRST answer, replayed
    assert len(marks_of(api, BATCH_NEW).json()["marks"]) == 1     # saved once
    assert len(custodians.calls) == 1                             # the replay did not even need the Script service


def test_a_retry_still_works_while_the_script_service_is_down(api, custodians):
    first = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("retry-key-2"), json=bulk(("CN0001", 50)))
    custodians.down = True
    again = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("retry-key-2"), json=bulk(("CN0001", 50)))
    assert again.status_code == 201 and again.json() == first.json()


def test_the_same_key_for_a_different_request_is_422(api):
    api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("shared-key"), json=bulk(("CN0001", 50)))
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("shared-key"), json=bulk(("CN0001", 51)))
    assert response.status_code == 422
    assert marks_of(api, BATCH_NEW).json()["marks"][0]["current_score"] == 50


def test_a_mark_that_was_already_entered_is_never_overwritten(api):
    api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("first-key"), json=bulk(("CN0001", 50)))
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("other-key"),
                        json=bulk(("CN0001", 99), ("CN0002", 40)))
    assert response.status_code == 409
    marks = marks_of(api, BATCH_NEW).json()["marks"]
    assert [(m["candidate_number"], m["current_score"]) for m in marks] == [("CN0001", 50)]   # nothing partial either


def test_more_marks_can_be_added_for_other_candidates(api):
    api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("first-key"), json=bulk(("CN0001", 50)))
    response = api.post(URL, as_=EXAMINER_ONE, batch_id=BATCH_NEW, headers=key("other-key"), json=bulk(("CN0002", 40)))
    assert response.status_code == 201
    assert [m["candidate_number"] for m in marks_of(api, BATCH_NEW).json()["marks"]] == ["CN0001", "CN0002"]


def test_approved_marks_are_locked_even_for_the_custodian(api):
    # MTH101 is approved in the seed; examiner 2 is its custodian
    response = api.post(URL, as_=EXAMINER_TWO, batch_id=BATCH_MTH101, headers=key(), json=bulk(("CN2009", 50)))
    assert response.status_code == 409
    assert len(marks_of(api, BATCH_MTH101).json()["marks"]) == 2
