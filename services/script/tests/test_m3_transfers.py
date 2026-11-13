"""M3 -- custody transfers: start a handover, accept it, the rules around them."""
import pytest

from tests.conftest import (BATCH_CSC201, BATCH_MTH101, BATCH_NET301, EXAMINER_1_ID, EXAMINER_2_ID,
                            EXAMINER_ONE, EXAMINER_RETIRED, EXAMINER_TWO, FIRST_NEW_ID, FROZEN_CREATED,
                            MODERATOR, MODERATOR_ID, OFFICER, OFFICER_ID, TRANSFER_ACCEPTED,
                            TRANSFER_KEYS_PENDING, TRANSFER_PENDING, UNKNOWN_BATCH, UNKNOWN_TRANSFER,
                            UNKNOWN_USER, new_batch)

pytestmark = pytest.mark.m3


def history(api, batch_id):
    return api.get("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=batch_id).json()["transfers"]


def custodian(api, batch_id):
    return api.get("/v1/batches/{batch_id}/custodian", as_=OFFICER, batch_id=batch_id).json()["custodian_id"]


# ---- start a transfer -----------------------------------------------------------------------
def test_start_transfer_creates_a_pending_transfer(api):
    response = api.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_NET301,
                        json={"to_user_id": EXAMINER_1_ID})
    assert response.status_code == 201
    transfer = response.json()
    assert set(transfer) == TRANSFER_KEYS_PENDING                      # no responded_at yet
    assert transfer["id"] == FIRST_NEW_ID
    assert transfer["batch_id"] == BATCH_NET301
    assert transfer["from_user_id"] == OFFICER_ID
    assert transfer["to_user_id"] == EXAMINER_1_ID
    assert transfer["status"] == "pending"
    assert transfer["requested_at"] == FROZEN_CREATED
    assert custodian(api, BATCH_NET301) == OFFICER_ID                  # nothing moves until it is accepted
    assert [t["id"] for t in history(api, BATCH_NET301)] == [FIRST_NEW_ID]


def test_only_the_current_custodian_can_start_a_transfer(api):
    # examiner 2 is a valid examiner but NOT the custodian of NET301 (the officer is)
    response = api.post("/v1/batches/{batch_id}/transfers", as_=EXAMINER_TWO, batch_id=BATCH_NET301,
                        json={"to_user_id": EXAMINER_1_ID})
    assert response.status_code == 409
    assert history(api, BATCH_NET301) == []


def test_a_batch_has_at_most_one_pending_transfer(api):
    # MTH101 already has a pending transfer (seed): its custodian cannot start a second one
    response = api.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_MTH101,
                        json={"to_user_id": EXAMINER_1_ID})
    assert response.status_code == 409
    assert len(history(api, BATCH_MTH101)) == 1


def test_a_batch_cannot_be_handed_to_its_own_custodian(api):
    # examiner 1 holds CSC201 and is a valid receiver: handing it to himself is refused
    response = api.post("/v1/batches/{batch_id}/transfers", as_=EXAMINER_ONE, batch_id=BATCH_CSC201,
                        json={"to_user_id": EXAMINER_1_ID})
    assert response.status_code == 422
    assert len(history(api, BATCH_CSC201)) == 1


@pytest.mark.parametrize("receiver, why", [
    (UNKNOWN_USER, "the receiver does not exist"),
    (EXAMINER_RETIRED, "the receiver is not active"),
    (MODERATOR_ID, "the receiver is not an examiner"),
])
def test_the_receiver_must_be_an_active_examiner(api, receiver, why):
    response = api.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_NET301,
                        json={"to_user_id": receiver})
    assert response.status_code == 422, why
    assert history(api, BATCH_NET301) == []


def test_when_auth_is_down_the_transfer_fails_closed_with_503(api_auth_down):
    response = api_auth_down.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_NET301,
                                  json={"to_user_id": EXAMINER_1_ID})
    assert response.status_code == 503
    assert history(api_auth_down, BATCH_NET301) == []


def test_start_transfer_on_an_unknown_batch_is_404_and_a_malformed_body_is_422(api):
    response = api.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=UNKNOWN_BATCH,
                        json={"to_user_id": EXAMINER_1_ID})
    assert response.status_code == 404
    response = api.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=BATCH_NET301,
                        json={"to_user_id": "not-a-uuid"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "to_user_id"]


# ---- accept a transfer ----------------------------------------------------------------------
def test_accept_moves_the_custody_to_the_receiver(api):
    response = api.post("/v1/transfers/{transfer_id}/accept", as_=EXAMINER_TWO, transfer_id=TRANSFER_PENDING)
    assert response.status_code == 200
    transfer = response.json()
    assert transfer["status"] == "accepted"
    assert transfer["responded_at"] == FROZEN_CREATED
    assert custodian(api, BATCH_MTH101) == EXAMINER_2_ID
    assert history(api, BATCH_MTH101)[0]["status"] == "accepted"        # history is kept, never deleted


def test_only_the_named_receiver_can_accept(api):
    response = api.post("/v1/transfers/{transfer_id}/accept", as_=EXAMINER_ONE, transfer_id=TRANSFER_PENDING)
    assert response.status_code == 409
    assert history(api, BATCH_MTH101)[0]["status"] == "pending"
    assert custodian(api, BATCH_MTH101) == OFFICER_ID


def test_a_resolved_transfer_cannot_be_accepted_again(api):
    response = api.post("/v1/transfers/{transfer_id}/accept", as_=EXAMINER_ONE, transfer_id=TRANSFER_ACCEPTED)
    assert response.status_code == 409


def test_accept_an_unknown_transfer_is_404_and_a_malformed_id_is_422(api):
    response = api.post("/v1/transfers/{transfer_id}/accept", as_=EXAMINER_ONE, transfer_id=UNKNOWN_TRANSFER)
    assert response.status_code == 404
    response = api.post("/v1/transfers/{transfer_id}/accept", as_=EXAMINER_ONE, transfer_id="nope")
    assert response.status_code == 422


# ---- the whole story ------------------------------------------------------------------------
def test_full_custody_chain_officer_to_examiner_to_examiner(api):
    batch = api.post("/v1/batches", as_=OFFICER, json=new_batch()).json()
    bid = batch["id"]
    first = api.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=bid,
                     json={"to_user_id": EXAMINER_1_ID}).json()
    api.post("/v1/transfers/{transfer_id}/accept", as_=EXAMINER_ONE, transfer_id=first["id"])
    assert custodian(api, bid) == EXAMINER_1_ID
    # the officer is no longer the custodian: he cannot hand the batch over any more
    refused = api.post("/v1/batches/{batch_id}/transfers", as_=OFFICER, batch_id=bid,
                       json={"to_user_id": EXAMINER_2_ID})
    assert refused.status_code == 409
    second = api.post("/v1/batches/{batch_id}/transfers", as_=EXAMINER_ONE, batch_id=bid,
                      json={"to_user_id": EXAMINER_2_ID}).json()
    api.post("/v1/transfers/{transfer_id}/accept", as_=EXAMINER_TWO, transfer_id=second["id"])
    assert custodian(api, bid) == EXAMINER_2_ID
    chain = history(api, bid)
    assert [(t["from_user_id"], t["to_user_id"], t["status"]) for t in chain] == [
        (OFFICER_ID, EXAMINER_1_ID, "accepted"), (EXAMINER_1_ID, EXAMINER_2_ID, "accepted")]
