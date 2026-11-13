"""M2 -- POST /v1/batches: create a batch (request validation, store.create_batch)."""
import pytest

from tests.conftest import (BATCH_KEYS, FIRST_NEW_ID, FROZEN_CREATED, NEW_IDS, OFFICER,
                            OFFICER_ID, ids, new_batch)

pytestmark = pytest.mark.m2


def test_create_batch_answers_201_with_the_representation(api):
    response = api.post("/v1/batches", as_=OFFICER, json=new_batch())
    assert response.status_code == 201
    batch = response.json()
    assert set(batch) == BATCH_KEYS
    if batch["id"] != FIRST_NEW_ID:                  # the id is random when it is not injected
        pytest.fail("the id must come from the store's injected id factory: call self.new_id() FIRST",
                    pytrace=False)
    assert batch["created_at"] == FROZEN_CREATED     # from the injected clock, UTC, "Z"
    assert batch["course_code"] == "CSC201"
    assert batch["script_count"] == 3
    assert batch["created_by"] == OFFICER_ID
    assert batch["current_custodian_id"] == OFFICER_ID     # the officer holds the scripts at first


def test_one_script_is_created_per_candidate_number(api):
    created = api.post("/v1/batches", as_=OFFICER, json=new_batch()).json()
    scripts = api.get("/v1/batches/{batch_id}/scripts", as_=OFFICER, batch_id=created["id"]).json()["scripts"]
    assert [s["candidate_number"] for s in scripts] == ["CN0001", "CN0002", "CN0003"]    # sorted by the API
    assert {s["batch_id"] for s in scripts} == {created["id"]}
    # ids: the batch took NEW_IDS[0]; the scripts took the next ones IN THE ORDER GIVEN (CN0003, CN0001, CN0002)
    by_number = {s["candidate_number"]: s["id"] for s in scripts}
    assert by_number == {"CN0003": NEW_IDS[1], "CN0001": NEW_IDS[2], "CN0002": NEW_IDS[3]}


def test_new_batches_are_listed_first_and_get_ids_in_order(api):
    first = api.post("/v1/batches", as_=OFFICER, json=new_batch()).json()
    second = api.post("/v1/batches", as_=OFFICER, json=new_batch(course_code="MTH101",
                                                                  candidate_numbers=["CN0009"])).json()
    listed = ids(api.get("/v1/batches", as_=OFFICER, params={"limit": 100}))
    assert len(listed) == 5
    assert listed[:2] == [second["id"], first["id"]]
    assert second["created_at"] > first["created_at"]


@pytest.mark.parametrize("payload, loc", [
    (new_batch(course_code="csc201"), ["body", "course_code"]),
    (new_batch(course_code="CS2"), ["body", "course_code"]),
    (new_batch(session_label=""), ["body", "session_label"]),
    (new_batch(session_label="x" * 61), ["body", "session_label"]),
    (new_batch(candidate_numbers=[]), ["body", "candidate_numbers"]),
    (new_batch(candidate_numbers=["CN0001", "CN0001"]), ["body", "candidate_numbers"]),
    (new_batch(candidate_numbers=["CN12"]), ["body", "candidate_numbers", 0]),
    (new_batch(candidate_numbers=[f"CN{n:04d}" for n in range(201)]), ["body", "candidate_numbers"]),
    ({"session_label": "x", "candidate_numbers": ["CN0001"]}, ["body", "course_code"]),
])
def test_invalid_batches_are_rejected_with_422_and_nothing_is_stored(api, payload, loc):
    response = api.post("/v1/batches", as_=OFFICER, json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == loc
    assert len(ids(api.get("/v1/batches", as_=OFFICER, params={"limit": 100}))) == 3
