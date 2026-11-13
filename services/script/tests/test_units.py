"""Unit tests: the schemas and the store, WITHOUT HTTP.

They give you feedback on one piece at a time, before the routes exist:
  K1 -> response models   K2 -> store reads   F1 -> request model + create_batch   F2 -> transfers
Run them with  `make test-script`  or  `python -m pytest tests/test_units.py -v`.
"""
import copy
import json

import pytest
from pydantic import ValidationError

from app.errors import Conflict, NotFound, Unprocessable
from app.schemas import (BatchesSchema, BatchSchema, CreateBatchSchema, CreateTransferSchema, CustodianSchema,
                         ScriptsSchema, TransferSchema, TransfersSchema)
from app.store import SEED_PATH
from tests.conftest import (BATCH_CSC201, BATCH_KEYS, BATCH_MTH101, BATCH_NET301, EXAMINER_1_ID, EXAMINER_2_ID,
                            FROZEN_CREATED, NEW_IDS, OFFICER_ID, SCRIPT_KEYS, SEED_IDS_NEWEST_FIRST,
                            TRANSFER_ACCEPTED, TRANSFER_KEYS_PENDING, TRANSFER_PENDING, UNKNOWN_BATCH,
                            UNKNOWN_TRANSFER, make_store, new_batch)

SEED = json.loads(SEED_PATH.read_text(encoding="utf-8"))
CSC201, MTH101 = SEED[0], SEED[1]


def shown(model, data):
    """What a client would receive: validate through the model, then dump like FastAPI does."""
    return model.model_validate(data).model_dump(mode="json", exclude_none=True)


# =============================================================================== K1: response models
@pytest.mark.m1
def test_batch_schema_hides_the_scripts_and_the_transfers():
    assert set(shown(BatchSchema, CSC201)) == BATCH_KEYS


@pytest.mark.m1
def test_transfer_schema_omits_responded_at_while_pending():
    assert set(shown(TransferSchema, MTH101["transfers"][0])) == TRANSFER_KEYS_PENDING
    assert "responded_at" in shown(TransferSchema, CSC201["transfers"][0])


@pytest.mark.m1
def test_the_list_schemas_wrap_their_items():
    assert [b["id"] for b in shown(BatchesSchema, {"batches": SEED})["batches"]] == [b["id"] for b in SEED]
    assert set(shown(ScriptsSchema, {"scripts": CSC201["scripts"]})["scripts"][0]) == SCRIPT_KEYS
    assert len(shown(TransfersSchema, {"transfers": CSC201["transfers"]})["transfers"]) == 1
    assert shown(CustodianSchema, {"batch_id": BATCH_CSC201, "custodian_id": EXAMINER_1_ID}) == \
        {"batch_id": BATCH_CSC201, "custodian_id": EXAMINER_1_ID}


@pytest.mark.m1
def test_response_models_check_the_types():
    broken = copy.deepcopy(CSC201)
    broken["script_count"] = "many"
    with pytest.raises(ValidationError):
        BatchSchema.model_validate(broken)
    broken = copy.deepcopy(CSC201)
    broken["id"] = "not-a-uuid"
    with pytest.raises(ValidationError):
        BatchSchema.model_validate(broken)


# =============================================================================== K2: store reads
@pytest.mark.m1
def test_store_list_batches_newest_first_filtered_and_sliced():
    store = make_store()
    assert [b["id"] for b in store.list_batches()] == SEED_IDS_NEWEST_FIRST
    assert [b["id"] for b in store.list_batches(course_code="MTH101")] == [BATCH_MTH101]
    assert [b["id"] for b in store.list_batches(limit=1, offset=1)] == [BATCH_MTH101]
    assert store.list_batches(offset=3) == []


@pytest.mark.m1
def test_store_hands_out_copies_not_the_stored_records():
    store = make_store()
    store.get_batch(BATCH_CSC201)["course_code"] = "HACKED"
    store.list_batches()[0]["course_code"] = "HACKED"
    store.list_scripts(BATCH_CSC201)[0]["candidate_number"] = "HACKED"
    assert store.get_batch(BATCH_CSC201)["course_code"] == "CSC201"
    assert store.list_batches()[0]["course_code"] == "NET301"
    assert store.list_scripts(BATCH_CSC201)[0]["candidate_number"] == "CN1001"


@pytest.mark.m1
def test_store_get_batch_scripts_custodian_and_history():
    store = make_store()
    assert store.get_batch(BATCH_CSC201)["script_count"] == 4
    assert [s["candidate_number"] for s in store.list_scripts(BATCH_CSC201, limit=2, offset=1)] == ["CN1002", "CN1003"]
    assert store.custodian_of(BATCH_CSC201) == EXAMINER_1_ID
    assert [t["id"] for t in store.list_transfers(BATCH_CSC201)] == [TRANSFER_ACCEPTED]
    assert store.list_transfers(BATCH_NET301) == []
    for read in (store.get_batch, store.list_scripts, store.custodian_of, store.list_transfers):
        with pytest.raises(NotFound):
            read(UNKNOWN_BATCH)


# =============================================================================== F1: create a batch
@pytest.mark.m2
def test_create_batch_schema_accepts_a_valid_payload():
    schema = CreateBatchSchema.model_validate(new_batch())
    assert schema.model_dump(mode="json") == new_batch()


@pytest.mark.m2
@pytest.mark.parametrize("changes", [
    {"course_code": "csc201"}, {"course_code": "CS2"}, {"session_label": ""}, {"session_label": "x" * 61},
    {"candidate_numbers": []}, {"candidate_numbers": ["CN0001", "CN0001"]}, {"candidate_numbers": ["CN12"]},
    {"candidate_numbers": [f"CN{n:04d}" for n in range(201)]},
])
def test_create_batch_schema_refuses_invalid_payloads(changes):
    with pytest.raises(ValidationError):
        CreateBatchSchema.model_validate(new_batch(**changes))


@pytest.mark.m2
def test_create_batch_schema_requires_its_three_fields():
    for missing in ("course_code", "session_label", "candidate_numbers"):
        payload = new_batch()
        del payload[missing]
        with pytest.raises(ValidationError):
            CreateBatchSchema.model_validate(payload)


@pytest.mark.m2
def test_store_create_batch():
    store = make_store()
    batch = store.create_batch(new_batch(), created_by=OFFICER_ID)
    assert batch["id"] == NEW_IDS[0]                         # the batch takes the FIRST id
    assert batch["created_at"] == FROZEN_CREATED
    assert (batch["script_count"], batch["created_by"], batch["current_custodian_id"]) == (3, OFFICER_ID, OFFICER_ID)
    assert batch["transfers"] == []
    assert [(s["candidate_number"], s["id"]) for s in batch["scripts"]] == [
        ("CN0003", NEW_IDS[1]), ("CN0001", NEW_IDS[2]), ("CN0002", NEW_IDS[3])]    # then one id per script, in order
    assert all(s["batch_id"] == batch["id"] for s in batch["scripts"])
    assert len(store) == 4 and store._find_batch(batch["id"]) == batch


# =============================================================================== F2: transfers
@pytest.mark.m3
def test_create_transfer_schema_needs_a_uuid():
    assert str(CreateTransferSchema.model_validate({"to_user_id": EXAMINER_1_ID}).to_user_id) == EXAMINER_1_ID
    for bad in ({}, {"to_user_id": "nope"}, {"to_user_id": None}):
        with pytest.raises(ValidationError):
            CreateTransferSchema.model_validate(bad)


@pytest.mark.m3
def test_store_request_transfer():
    store = make_store()
    transfer = store.request_transfer(BATCH_NET301, EXAMINER_1_ID, OFFICER_ID)
    assert transfer == {"id": NEW_IDS[0], "batch_id": BATCH_NET301, "from_user_id": OFFICER_ID,
                        "to_user_id": EXAMINER_1_ID, "status": "pending", "requested_at": FROZEN_CREATED}
    assert store._find_batch(BATCH_NET301)["transfers"] == [transfer]
    assert store._find_batch(BATCH_NET301)["current_custodian_id"] == OFFICER_ID     # custody moves only when accepted


@pytest.mark.m3
def test_store_request_transfer_rules():
    store = make_store()
    with pytest.raises(NotFound):
        store.request_transfer(UNKNOWN_BATCH, EXAMINER_1_ID, OFFICER_ID)
    with pytest.raises(Conflict):                                   # not the custodian
        store.request_transfer(BATCH_NET301, EXAMINER_1_ID, EXAMINER_2_ID)
    with pytest.raises(Unprocessable):                              # custodian hands it to himself
        store.request_transfer(BATCH_CSC201, EXAMINER_1_ID, EXAMINER_1_ID)
    with pytest.raises(Conflict):                                   # MTH101 already has a pending transfer
        store.request_transfer(BATCH_MTH101, EXAMINER_1_ID, OFFICER_ID)
    assert len(store._find_batch(BATCH_MTH101)["transfers"]) == 1


@pytest.mark.m3
def test_store_accept_transfer():
    store = make_store()
    transfer = store.accept_transfer(TRANSFER_PENDING, EXAMINER_2_ID)
    assert (transfer["status"], transfer["responded_at"]) == ("accepted", FROZEN_CREATED)
    assert store._find_batch(BATCH_MTH101)["current_custodian_id"] == EXAMINER_2_ID
    assert store._find_batch(BATCH_MTH101)["transfers"][0]["status"] == "accepted"   # history is kept


@pytest.mark.m3
def test_store_accept_transfer_rules():
    store = make_store()
    with pytest.raises(NotFound):
        store.accept_transfer(UNKNOWN_TRANSFER, EXAMINER_1_ID)
    with pytest.raises(Conflict):                                   # not the named receiver
        store.accept_transfer(TRANSFER_PENDING, EXAMINER_1_ID)
    with pytest.raises(Conflict):                                   # already resolved
        store.accept_transfer(TRANSFER_ACCEPTED, EXAMINER_1_ID)
    assert store._find_batch(BATCH_MTH101)["transfers"][0]["status"] == "pending"
    assert store._find_batch(BATCH_MTH101)["current_custodian_id"] == OFFICER_ID
