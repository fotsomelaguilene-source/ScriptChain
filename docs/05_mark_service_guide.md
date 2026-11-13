# 05 · Mark Service guide: how to write every TODO

Folder: `services/mark/`. Same method as the Script guide (`04`): **read it first**, the loop is identical.
This service is *harder* in three places: the **custodian check** (it depends on another service), **idempotency**,
and **locking after approval**. The read tasks (K1–K3) are the same kind as in the Script service: this time Kelly does them
with **less help** — that is how you check you really learned.

| Task | Owner | What | Files | Done when |
|---|---|---|---|---|
| **K6** (= K1+K2+K3 again) | Kelly | response models, 5 store reads, 5 read routes | `schemas.py`, `store.py`, `api.py` (`TODO M1`) | `pytest -m m1` green |
| **K4** | Kelly | security tests | `tests/test_m4_security.py` | `pytest -m m4` green |
| **K5** | Kelly | `HttpCustodianClient` (timeouts, retries) + its tests | `app/ports.py`, `tests/test_m5_http_client.py` | `pytest -m m5` green |
| **F3** | Franck | bulk submission: request models, `submit_marks`, route | `schemas.py`, `store.py`, `api.py` (`TODO M2`) | `pytest -m m2` green |
| **F4** | Franck | adjust + approve: request model, 2 store methods, 2 routes | (`TODO M3`) | `pytest -m m3` green |

Dependency: like the Script service, API tests of F3/F4 need the read routes (K6). Franck starts with the unit tests
(`pytest tests/test_units.py -m m2`, `-m m3`).

---
## K6 · The read side (`TODO M1`) — Kelly, ~5 h, no step-by-step this time

Use the recipes of the Script guide (K1, K2, K3). Only the *facts* change:

* **Response models** (`schemas.py`): `MarkSchema` (8 fields — do **not** declare `adjustments`), `MarksSchema`, `BulkResultSchema`,
  `AdjustmentSchema`, `AdjustmentsSchema`, `PendingBatchSchema`, `PendingSchema`, `ApprovalSchema`. Scores are `float`.
  Statuses use the enum `BatchMarkStatus`.
* **Store reads**: `list_marks`, `get_mark`, `list_adjustments`, `pending`, `get_approval`. Two helpers are provided: `_find_batch`
  (by *script batch id*) and `_find_mark` (returns **two** things: the mark batch and the mark → `_batch, mark = self._find_mark(id)`).
  `pending()` builds *new small dicts* `{"batch_id", "status", "mark_count"}` — the first time you build a dict yourself.
* **Routes**: `getMarks`, `getMark`, `getAdjustments`, `getPending` (only `moderator` and `hod`: the alias `ModeratorOrHod` exists), `getApproval`.

Checks: `pytest tests/test_units.py -m m1` then `pytest -m m1`.

---
## K5 · `HttpCustodianClient` (`app/ports.py`, `TODO M5`) — Kelly, ~3 h  *(networking: your home ground)*

**Why it exists.** Before saving marks, Mark asks Script *"who holds this batch?"* over HTTP:
`GET {SCRIPT_URL}/v1/batches/{batch_id}/custodian` with the caller's token. A network call can be slow, can fail, can be refused.
The brief asks us to **pick one timeout, document it, retry only safe reads a small fixed number of times, and test the timeout path.**
This task is exactly that.

**Rules** (they are in the docstring and in the tests):

| What Script answers | What the client does |
|---|---|
| `200` + `{"custodian_id": ...}` | return the id |
| `404` | raise `BatchNotFound` — **no retry** |
| `401` / `403` / other `4xx` | raise `ScriptServiceUnavailable` — **no retry** (asking again will not help; and we must not accept unverified marks) |
| `5xx` | try again |
| timeout / connection refused (`httpx.TransportError`) | try again |
| still failing after `1 + retries` attempts | raise `ScriptServiceUnavailable` (**fail closed**) |

**Steps.**
1. Read the `__init__` (given): it builds an `httpx.Client` with the timeout. `transport=` lets tests replace the network.
2. Write `get_custodian`: a `for attempt in range(self.retries + 1):` loop; inside, `try: response = self._client.get(url, headers=...)`
   and `except httpx.TransportError: continue`; then look at `response.status_code` as in the table.
3. **Write the tests first or together:** open `tests/test_m5_http_client.py`. `FakeNetwork` plays the Script service (you give it a list of
   answers or errors; it counts the requests). The first test is a worked example; **complete the six `TODO K5` tests** following the hints.
   Notice how a test *proves* "3 attempts" simply by counting `network.requests`.
4. Run `python -m pytest -q -m m5`.

Questions for the report: *Why is retrying a `POST` that creates something dangerous but retrying this `GET` fine? What value did you pick for the
timeout, and why? What would exponential back-off add? What happens to the examiner's request while the retries run?*

---
## F3 · Bulk submission (`TODO M2`) — Franck, ~5 h

1. **Request models**: `MarkEntrySchema` (`candidate_number`, `score` — use the ready-made `Score` type: `float`, strict, 0–100, so `"50"` and
   `true` are refused) and `BulkMarksSchema` (`entries` 1–500 + a validator refusing the same candidate twice).
2. **`submit_marks`** in the store. Follow the docstring. Two details the tests check: the **mark batch takes the first id, but only when it is
   created**, then one id per mark; and **one** `self.clock()` reading for the whole call.
3. **The route** — the heart of the project. In this exact order:
   1. fingerprint the request; 2. look for the Idempotency-Key (same key + other request → 422; same key + same request → replay the first answer);
   3. ask the custodian (`BatchNotFound` → 404, `ScriptServiceUnavailable` → 503); 4. not the custodian → 409; 5. save; 6. remember the answer.

   Why the replay comes **before** the custodian check: a client that did not receive the first answer must be able to retry safely **even
   if the Script service is down now** (test `test_a_retry_still_works_while_the_script_service_is_down`).

Checks: `pytest tests/test_units.py -m m2` then `pytest -m m2`.

## F4 · Moderation and approval (`TODO M3`) — Franck, ~3 h

1. `AdjustmentRequestSchema`: `model_config = ConfigDict(str_strip_whitespace=True)` so a reason made of spaces becomes empty and fails `min_length=1`.
2. `add_adjustment`: rules in order (exists, not locked), then record `old_score` = the CURRENT score, set the new one, `original_score` never changes,
   first adjustment moves the batch to `in_moderation`. `approve`: exists, not already approved, set status + approval record.
3. Routes `adjustMark` (role `Moderator`) and `approveBatch` (role `Hod`).

Checks: `pytest tests/test_units.py -m m3` then `pytest -m m3`.

---
## K4 · Security tests for Mark — Kelly, ~1 h (you already did the Script version)
Same four loops in `tests/test_m4_security.py` (the table has 8 operations; this time headers are part of the table because of the Idempotency-Key).

## The finish line: both services together
When *everything* is green in both services:
```
make run-script        # terminal 1
make run-mark          # terminal 2
make demo              # terminal 3: 9 real HTTP steps; every line must say [OK ]
```
Demo failing at step 4 ("submits marks")? Either `HttpCustodianClient` (K5) is unfinished, or the Script service is not running on port 8001.
