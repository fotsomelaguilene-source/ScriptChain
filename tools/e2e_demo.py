"""End-to-end demo of the whole story through REAL HTTP, with the two services running:

    terminal 1:  make run-script        (port 8001)
    terminal 2:  make run-mark          (port 8002)
    terminal 3:  make demo

Officer creates a batch -> hands it to an examiner -> examiner accepts -> enters marks (the Mark service asks
the Script service who the custodian is) -> a retry with the same key -> a moderator adjusts -> the HOD approves
-> the marks are locked. It needs ALL milestones finished, including K5 (HttpCustodianClient).
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_token import USERS, token_for  # noqa: E402

SCRIPT, MARK = "http://127.0.0.1:8001", "http://127.0.0.1:8002"
bearer = lambda role, nth=1: {"Authorization": f"Bearer {token_for(role, nth)}"}      # noqa: E731
step_no = 0


def step(title: str, response: httpx.Response, expect: int):
    global step_no
    step_no += 1
    mark = "OK " if response.status_code == expect else "BAD"
    print(f"{step_no:2}. [{mark}] {response.status_code} (wanted {expect})  {title}")
    if response.status_code != expect:
        print("    ", response.text[:300]); sys.exit(1)
    return response.json() if response.content else None


examiner1 = next(u["id"] for u in USERS if u["role"] == "examiner")
batch = step("officer creates a batch", httpx.post(f"{SCRIPT}/v1/batches", headers=bearer("officer"), json={
    "course_code": "CSC201", "session_label": "Demo session", "candidate_numbers": ["CN7001", "CN7002", "CN7003"]}), 201)
bid = batch["id"]
transfer = step("officer hands the batch to examiner 1", httpx.post(f"{SCRIPT}/v1/batches/{bid}/transfers",
                headers=bearer("officer"), json={"to_user_id": examiner1}), 201)
step("examiner 1 accepts", httpx.post(f"{SCRIPT}/v1/transfers/{transfer['id']}/accept", headers=bearer("examiner")), 200)
marks = {"entries": [{"candidate_number": "CN7001", "score": 55}, {"candidate_number": "CN7002", "score": 71.5}]}
key = {"Idempotency-Key": f"demo-{bid[:8]}"}
saved = step("examiner 1 submits marks", httpx.post(f"{MARK}/v1/batches/{bid}/marks/bulk",
             headers={**bearer("examiner"), **key}, json=marks), 201)
step("same request again (retry): same answer, nothing saved twice", httpx.post(f"{MARK}/v1/batches/{bid}/marks/bulk",
     headers={**bearer("examiner"), **key}, json=marks), 201)
step("examiner 2 is NOT the custodian: refused", httpx.post(f"{MARK}/v1/batches/{bid}/marks/bulk",
     headers={**bearer("examiner", 2), "Idempotency-Key": "demo-other-key"}, json=marks), 409)
mid = saved["marks"][0]["id"]
step("moderator adjusts a mark", httpx.post(f"{MARK}/v1/marks/{mid}/adjustments", headers=bearer("moderator"),
     json={"new_score": 58, "reason": "Question 3 was under-marked"}), 201)
step("HOD approves the batch", httpx.post(f"{MARK}/v1/batches/{bid}/approval", headers=bearer("hod")), 201)
step("marks are locked: adjustment refused", httpx.post(f"{MARK}/v1/marks/{mid}/adjustments", headers=bearer("moderator"),
     json={"new_score": 99, "reason": "too late"}), 409)
print("\nWhole workflow works end to end.")
