"""M4 -- security: no token / bad token -> 401, wrong role -> 403 (task K4, written by KELLY).

The project brief demands at least ONE denied-access test for EVERY protected operation.
The table OPERATIONS below lists all eight operations of the Script service, with the roles
the specification allows. The worked example (first test) is given; the other four tests are
yours to write -- each is a loop over the table. Guide: docs/04_script_service_guide.md, task K4.

Remember: 401 = "I do not know who you are" (no/invalid token); 403 = "I know who you are, but
your role may not do this".
"""
import pytest

from tests.conftest import (BATCH_CSC201, BATCH_NET301, EXAMINER_2_ID, EXAMINER_ONE, EXAMINER_TWO, HOD,
                            MODERATOR, OFFICER, TRANSFER_PENDING, make_token, new_batch)

pytestmark = pytest.mark.m4

ALL_ROLES = ("exams_officer", "examiner", "moderator", "hod")
ACTOR_FOR_ROLE = {"exams_officer": OFFICER, "examiner": EXAMINER_ONE, "moderator": MODERATOR, "hod": HOD}

# (name, method, path template, path values, json body, roles the specification allows)
OPERATIONS = [
    ("getBatches", "GET", "/v1/batches", {}, None, ALL_ROLES),
    ("createBatch", "POST", "/v1/batches", {}, new_batch(), ("exams_officer",)),
    ("getBatch", "GET", "/v1/batches/{batch_id}", {"batch_id": BATCH_CSC201}, None, ALL_ROLES),
    ("getScripts", "GET", "/v1/batches/{batch_id}/scripts", {"batch_id": BATCH_CSC201}, None, ALL_ROLES),
    ("getTransfers", "GET", "/v1/batches/{batch_id}/transfers", {"batch_id": BATCH_CSC201}, None, ALL_ROLES),
    ("startTransfer", "POST", "/v1/batches/{batch_id}/transfers", {"batch_id": BATCH_NET301},
     {"to_user_id": EXAMINER_2_ID}, ("exams_officer", "examiner")),
    ("getCustodian", "GET", "/v1/batches/{batch_id}/custodian", {"batch_id": BATCH_CSC201}, None, ALL_ROLES),
    ("acceptTransfer", "POST", "/v1/transfers/{transfer_id}/accept", {"transfer_id": TRANSFER_PENDING},
     None, ("examiner",)),
]


def test_create_batch_without_a_token_is_401(api):
    """WORKED EXAMPLE (given). Study it: the other tests are the same idea, in a loop."""
    response = api.post("/v1/batches", json=new_batch())          # no as_=..., no token=...: no header at all
    assert response.status_code == 401


def test_no_token_is_401_for_every_operation(api):
    """Loop over OPERATIONS: call each one with NO token and expect 401."""
    # TODO K4: for name, method, template, values, body, allowed in OPERATIONS:
    #     response = api.call(method, template, json=body, **values)
    #     assert response.status_code == 401, name
    pytest.fail("TODO K4: loop over OPERATIONS and expect 401 when no token is sent", pytrace=False)


@pytest.mark.parametrize("kind", ["garbage", "expired", "forged", "unknown_role", "subject_not_a_uuid"])
def test_bad_tokens_are_401(api, kind):
    """A token that is present but not acceptable must be refused with 401 (try it on getBatches)."""
    # TODO K4: build the bad token according to `kind`, then call GET /v1/batches with token=<it>:
    #   "garbage"            -> the text "not.a.jwt"
    #   "expired"            -> make_token(OFFICER, expires_in=-60)
    #   "forged"             -> make_token(OFFICER, secret="another-secret-long-enough-0123456789")     (signed with the WRONG key)
    #   "unknown_role"       -> make_token(OFFICER, role="student")             (extra keyword arguments replace claims)
    #   "subject_not_a_uuid" -> make_token(OFFICER, sub="admin")
    # Expect 401 each time.
    pytest.fail(f"TODO K4: build a '{kind}' token and expect 401", pytrace=False)


def test_wrong_role_is_403_for_every_protected_write(api):
    """For every operation, every role that is NOT allowed must get 403."""
    # TODO K4: for each operation of OPERATIONS and each role in ALL_ROLES that is NOT in `allowed`:
    #     response = api.call(method, template, as_=ACTOR_FOR_ROLE[role], json=body, **values)
    #     assert response.status_code == 403, (name, role)
    # (the read operations allow all four roles, so only the three write operations produce 403s)
    pytest.fail("TODO K4: loop over operations and forbidden roles, expect 403", pytrace=False)


def test_every_allowed_role_gets_past_the_security_check(api):
    """The other side of the coin: an ALLOWED role must never get 401 or 403 (404/409/422 are fine)."""
    # TODO K4: for each operation and each role in `allowed`:
    #     response = api.call(method, template, as_=ACTOR_FOR_ROLE[role], json=body, **values)
    #     assert response.status_code not in (401, 403), (name, role)
    pytest.fail("TODO K4: loop over operations and allowed roles, expect neither 401 nor 403", pytrace=False)
