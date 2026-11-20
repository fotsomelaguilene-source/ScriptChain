"""M4 -- security: no token / bad token -> 401, wrong role -> 403 (task K4, written by KELLY).

The project brief demands at least ONE denied-access test for EVERY protected operation.
The table OPERATIONS lists all eight operations of the Mark service with the roles the specification
allows. The worked example (first test) is given; the other four tests are yours to write -- each is a
loop over the table. Guide: docs/05_mark_service_guide.md, task K4 (same idea as in the Script service).
"""
import pytest

from tests.conftest import (BATCH_CSC201, BATCH_NEW, EXAMINER_ONE, HOD, MARK_CN1001, MODERATOR, OFFICER, bulk, key,
                            make_token)

pytestmark = pytest.mark.m4

ALL_ROLES = ("exams_officer", "examiner", "moderator", "hod")
ACTOR_FOR_ROLE = {"exams_officer": OFFICER, "examiner": EXAMINER_ONE, "moderator": MODERATOR, "hod": HOD}

# (name, method, path template, path values, json body, extra headers, roles the specification allows)
OPERATIONS = [
    ("submitMarks", "POST", "/v1/batches/{batch_id}/marks/bulk", {"batch_id": BATCH_NEW}, bulk(("CN0001", 50)),
     key(), ("examiner",)),
    ("getMarks", "GET", "/v1/batches/{batch_id}/marks", {"batch_id": BATCH_CSC201}, None, None, ALL_ROLES),
    ("getMark", "GET", "/v1/marks/{mark_id}", {"mark_id": MARK_CN1001}, None, None, ALL_ROLES),
    ("adjustMark", "POST", "/v1/marks/{mark_id}/adjustments", {"mark_id": MARK_CN1001},
     {"new_score": 65, "reason": "test"}, None, ("moderator",)),
    ("getAdjustments", "GET", "/v1/marks/{mark_id}/adjustments", {"mark_id": MARK_CN1001}, None, None, ALL_ROLES),
    ("getPending", "GET", "/v1/moderation/pending", {}, None, None, ("moderator", "hod")),
    ("approveBatch", "POST", "/v1/batches/{batch_id}/approval", {"batch_id": BATCH_CSC201}, None, None, ("hod",)),
    ("getApproval", "GET", "/v1/batches/{batch_id}/approval", {"batch_id": BATCH_CSC201}, None, None, ALL_ROLES),
]


def test_approve_without_a_token_is_401(api):
    """WORKED EXAMPLE (given). Study it: the other tests are the same idea, in a loop."""
    response = api.post("/v1/batches/{batch_id}/approval", batch_id=BATCH_CSC201)     # no as_=..., no token=...
    assert response.status_code == 401


def test_no_token_is_401_for_every_operation(api):
    """Loop over OPERATIONS: call each one with NO token and expect 401."""
    for name, method, template, values, body, headers, allowed in OPERATIONS:
        response = api.call(method, template, json=body, headers=headers, **values)
        assert response.status_code == 401, name


@pytest.mark.parametrize("kind", ["garbage", "expired", "forged", "unknown_role", "subject_not_a_uuid"])
def test_bad_tokens_are_401(api, kind):
    """A token that is present but not acceptable must be refused with 401 (try it on getMarks)."""
    bad_tokens = {
        "garbage": "not.a.jwt",
        "expired": make_token(EXAMINER_ONE, expires_in=-60),
        "forged": make_token(EXAMINER_ONE, secret="another-secret-long-enough-0123456789"),    # the WRONG key
        "unknown_role": make_token(EXAMINER_ONE, role="student"),
        "subject_not_a_uuid": make_token(EXAMINER_ONE, sub="admin"),
    }
    response = api.get("/v1/batches/{batch_id}/marks", token=bad_tokens[kind], batch_id=BATCH_CSC201)
    assert response.status_code == 401


def test_wrong_role_is_403_for_every_protected_operation(api):
    """For every operation, every role that is NOT allowed must get 403."""
    for name, method, template, values, body, headers, allowed in OPERATIONS:
        for role in ALL_ROLES:
            if role in allowed:
                continue
            response = api.call(method, template, as_=ACTOR_FOR_ROLE[role], json=body, headers=headers, **values)
            assert response.status_code == 403, (name, role)


def test_every_allowed_role_gets_past_the_security_check(api):
    """The other side of the coin: an ALLOWED role must never get 401 or 403 (404/409/422 are fine)."""
    for name, method, template, values, body, headers, allowed in OPERATIONS:
        for role in allowed:
            response = api.call(method, template, as_=ACTOR_FOR_ROLE[role], json=body, headers=headers, **values)
            assert response.status_code not in (401, 403), (name, role)
