"""M1 -- the read operations: list batches, one batch, its scripts, its custody history, its custodian.

These tests use the SEED batches only (data/seed.json), so they do not need M2 or M3.
"""
import pytest

from tests.conftest import (BATCH_CSC201, BATCH_KEYS, BATCH_MTH101, BATCH_NET301, EXAMINER_1_ID,
                            OFFICER, OFFICER_ID, SCRIPT_KEYS, SEED_IDS_NEWEST_FIRST,
                            TRANSFER_KEYS_PENDING, UNKNOWN_BATCH, ids)

pytestmark = pytest.mark.m1


# ---- list of batches ------------------------------------------------------------------------
def test_list_returns_the_three_seed_batches_newest_first(api):
    response = api.get("/v1/batches", as_=OFFICER)
    assert response.status_code == 200
    assert ids(response) == SEED_IDS_NEWEST_FIRST
    assert response.json()["batches"][0]["course_code"] == "NET301"


def test_course_filter(api):
    assert ids(api.get("/v1/batches", as_=OFFICER, params={"course_code": "MTH101"})) == [BATCH_MTH101]
    assert ids(api.get("/v1/batches", as_=OFFICER, params={"course_code": "ZZZ999"})) == []


def test_limit_and_offset(api):
    assert ids(api.get("/v1/batches", as_=OFFICER, params={"limit": 1})) == [BATCH_NET301]
    assert ids(api.get("/v1/batches", as_=OFFICER, params={"limit": 1, "offset": 1})) == [BATCH_MTH101]
    assert ids(api.get("/v1/batches", as_=OFFICER, params={"offset": 2})) == [BATCH_CSC201]


def test_invalid_query_parameters_are_rejected_with_422(api):
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"course_code": "abc"}):
        response = api.get("/v1/batches", as_=OFFICER, params=params)
        assert response.status_code == 422, params
        assert response.json()["detail"][0]["loc"] == ["query", next(iter(params))]


# ---- one batch ------------------------------------------------------------------------------
def test_get_batch_returns_the_csc201_batch(api):
    response = api.get("/v1/batches/{batch_id}", as_=OFFICER, batch_id=BATCH_CSC201)
    assert response.status_code == 200
    batch = response.json()
    assert batch["id"] == BATCH_CSC201
    assert batch["course_code"] == "CSC201"
    assert batch["script_count"] == 4
    assert batch["created_at"] == "2026-10-20T08:00:00Z"
    assert batch["created_by"] == OFFICER_ID
    assert batch["current_custodian_id"] == EXAMINER_1_ID


def test_batches_are_shown_without_their_internal_lists(api):
    """The stored batch holds 'scripts' and 'transfers'; the spec's BatchSchema does not show them."""
    for batch in api.get("/v1/batches", as_=OFFICER).json()["batches"]:
        assert set(batch) == BATCH_KEYS, batch["id"]
    assert set(api.get("/v1/batches/{batch_id}", as_=OFFICER, batch_id=BATCH_CSC201).json()) == BATCH_KEYS


def test_unknown_batch_is_404_with_its_id_in_the_detail(api):
    for template in ("/v1/batches/{batch_id}", "/v1/batches/{batch_id}/scripts",
                     "/v1/batches/{batch_id}/transfers", "/v1/batches/{batch_id}/custodian"):
        response = api.get(template, as_=OFFICER, batch_id=UNKNOWN_BATCH)
        assert response.status_code == 404, template
        assert response.json() == {"detail": f"Batch {UNKNOWN_BATCH} not found"}


def test_malformed_batch_id_is_422(api):
    response = api.get("/v1/batches/{batch_id}", as_=OFFICER, batch_id="not-a-uuid")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "batch_id"]


# ---- scripts --------------------------------------------------------------------------------
def test_scripts_are_ordered_by_candidate_number_and_paged(api):
    response = api.get("/v1/batches/{batch_id}/scripts", as_=OFFICER, batch_id=BATCH_CSC201,
                       params={"limit": 100})
    numbers = [script["candidate_number"] for script in response.json()["scripts"]]
    assert numbers == ["CN1001", "CN1002", "CN1003", "CN1004"]
    page = api.get("/v1/batches/{batch_id}/scripts", as_=OFFICER, batch_id=BATCH_CSC201,
                   params={"limit": 2, "offset": 1})
    assert [s["candidate_number"] for s in page.json()["scripts"]] == ["CN1002", "CN1003"]
    assert all(set(s) == SCRIPT_KEYS and s["batch_id"] == BATCH_CSC201 for s in page.json()["scripts"])


# ---- custodian ------------------------------------------------------------------------------
def test_custodian_of_a_batch(api):
    expected = {BATCH_CSC201: EXAMINER_1_ID, BATCH_MTH101: OFFICER_ID, BATCH_NET301: OFFICER_ID}
    for batch_id, custodian in expected.items():
        response = api.get("/v1/batches/{batch_id}/custodian", as_=OFFICER, batch_id=batch_id)
        assert response.status_code == 200
        assert response.json() == {"batch_id": batch_id, "custodian_id": custodian}


# ---- custody history ------------------------------------------------------------------------
def test_custody_history(api):
    history = api.get("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_CSC201).json()["transfers"]
    assert len(history) == 1
    assert history[0]["status"] == "accepted"
    assert history[0]["responded_at"] == "2026-10-20T09:00:00Z"
    assert api.get("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_NET301).json() == {"transfers": []}


def test_optional_fields_are_omitted_never_null(api):
    """A pending transfer has no responded_at: the key must be ABSENT, not null."""
    pending = api.get("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_MTH101).json()["transfers"][0]
    assert pending["status"] == "pending"
    assert set(pending) == TRANSFER_KEYS_PENDING
