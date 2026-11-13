# 04 · Script Service guide: how to write every TODO

Folder: `services/script/`. Run everything from there (`cd services/script`) or from the root with `make test-script`.

## How to work (the loop — never skip it)
1. Pick **one** TODO. Find it: `grep -rn "TODO M1" app/` (or use your editor's search).
2. Read the comment under it: it lists exactly what to write.
3. Write a few lines. Save.
4. Run the test named in the task: `python -m pytest -q tests/test_units.py -k "batch_schema"` (see each task).
5. Read the first failure **from the bottom** (crash course lesson 12). Fix. Repeat.
6. When the task's tests are green: `git add -A && git commit -m "K1: response models"` (see `07_teamwork_git.md`).

Useful commands (from `services/script/`):
```
python -m pytest -q                         everything
python -m pytest -q -m m1                   one milestone (m1 m2 m3 m4 contract)
python -m pytest -q tests/test_units.py     only the unit tests (no HTTP: fastest feedback)
python -m pytest -q -x --tb=short           stop at the first failure, short traceback
python -m pytest -q -k custodian            only tests whose name contains "custodian"
```

## Map of the tasks (who, what, which tests tell you it is done)

| Task | Owner | What | Files | Done when |
|---|---|---|---|---|
| **K1** | Kelly | 7 response models | `app/schemas.py` (`TODO M1`) | `pytest tests/test_units.py -m m1 -k schema` green |
| **K2** | Kelly | 5 store reads | `app/store.py` (`TODO M1`) | `pytest tests/test_units.py -m m1` green |
| **K3** | Kelly | 5 read routes | `app/api.py` (`TODO M1`) | `pytest -m m1` green (12 API tests + units) |
| **K4** | Kelly | security tests | `tests/test_m4_security.py` (`TODO K4`) | `pytest -m m4` green |
| **F1** | Franck | create a batch | `schemas.py`, `store.py`, `api.py` (`TODO M2`) | `pytest -m m2` green |
| **F2** | Franck | custody transfers | `schemas.py`, `store.py`, `api.py` (`TODO M3`) | `pytest -m m3` green |
| final | both | contract | — | `pytest` all green, including `-m contract` |

**Dependency to know:** the API tests of F1/F2 use the read routes (K3) to check results. So Franck starts with the
**unit tests** (`tests/test_units.py -m m2`, `-m m3`), which need nothing from Kelly, and runs the API tests once K3 is merged.

---
## K1 · Response models (`app/schemas.py`, `TODO M1`)  — Kelly, ~2 h

**Goal.** Make the answers of the API match the spec: right fields, right types, nothing more.
**Read first:** `docs/03` (dictionary YAML → Python) and the schemas `BatchSchema`, `ScriptSchema`, `TransferSchema`,
`CustodianSchema`, `BatchesSchema`, `ScriptsSchema`, `TransfersSchema` in the YAML (`components → schemas`).

Right now each class contains `model_config = ConfigDict(extra="allow")`: a *placeholder* that lets every stored field through.
**Replace it** with the real fields, in the order of the YAML.

Pattern (library example):
```python
class BookSchema(BaseModel):
    id: UUID
    title: str
    pages: int
    published: datetime
    subtitle: str | None = None         # not in "required" in the YAML
```
Steps:
1. `ScriptSchema`: `id`, `batch_id` (UUID), `candidate_number` (str).
2. `BatchSchema`: 7 fields. ⚠️ A stored batch also holds `scripts` and `transfers`. Do **not** declare them: a response model
   only shows what it declares. That is how we hide them.
3. `TransferSchema`: the status is the enum `TransferStatus` (already written at the top). `responded_at` is **optional**.
4. `CustodianSchema`, then the three list classes (`batches: list[BatchSchema]`, …).

Check: `python -m pytest -q tests/test_units.py -m m1 -k "schema or models"`
Common mistakes: forgetting that `responded_at` must be `datetime | None = None` · declaring `scripts` in `BatchSchema`.

---
## K2 · Store reads (`app/store.py`, `TODO M1`) — Kelly, ~3 h

**Goal.** Five methods that *read* the data: `list_batches`, `get_batch`, `list_scripts`, `custodian_of`, `list_transfers`.
**Study first** the provided helper `_find_batch` just above: it is the model for everything.

| Method | One-sentence recipe |
|---|---|
| `get_batch` | a **deep copy** of what `self._find_batch(batch_id)` returns (one line) |
| `custodian_of` | the `"current_custodian_id"` entry of the record `_find_batch` returns |
| `list_transfers` | find the batch, sort its `"transfers"` by `requested_at`, return deep copies |
| `list_scripts` | find the batch, sort its `"scripts"` by `candidate_number`, slice `[offset: offset + limit]`, deep copy |
| `list_batches` | sort `self._batches` by `created_at` newest first; if `course_code` is not `None` keep only that course; slice; deep copy |

Order for `list_batches`: **sort → filter → slice → copy** (the docstring says so; the tests check it).
Lessons to reread: 3 (sorted / comprehension / slicing) and 4 (deepcopy).

Check: `python -m pytest -q tests/test_units.py -m m1`
The test `test_store_hands_out_copies_not_the_stored_records` fails if you forgot `copy.deepcopy` somewhere.

---
## K3 · Read routes (`app/api.py`, `TODO M1`) — Kelly, ~3 h

**Goal.** Five path operations. `getBatch` is **given** except its body (worked example): do it first, then imitate it.
Each TODO comment states: method + path, success code, response model, parameters, and the line to return.

Pattern for a collection with paging (library):
```python
@router.get("/books", status_code=status.HTTP_200_OK, response_model=BooksSchema, response_model_exclude_none=True)
def list_books(store: Store, user: AnyUser,
               limit: Annotated[int, Query(ge=1, le=100)] = 10,
               offset: Annotated[int, Query(ge=0)] = 0):
    return {"books": store.list_books(limit=limit, offset=offset)}
```
Notes:
* `user: AnyUser` is **not used inside** the function — it is there to **trigger the JWT check** (401 without token).
* The answer is an **object with a list inside** (`{"batches": [...]}`), not a bare list: the spec says so. Returning a bare list is
  the classic Lab 2 mistake: FastAPI answers 500 `ResponseValidationError`.
* The `batch_id` path parameter is `UUID`, not `str` and not `object`: that is what makes `/v1/batches/not-a-uuid` a 422.
* Parameters without default first.

Check: `python -m pytest -q -m m1`. When it is green, **try it by hand**:
```
make run-script                                   # terminal 1
python tools/make_token.py officer                # terminal 2: copy the token
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8001/v1/batches
```
Open http://127.0.0.1:8001/docs and use **Authorize**.

---
## K4 · Security tests (`tests/test_m4_security.py`, `TODO K4`) — Kelly, ~2 h  *(your home ground)*

**Goal.** The brief demands at least one denied-access test per protected operation. You write them.
**First read `app/security.py` (80 lines) and answer in the report** (this is your security review):
1. What are the three parts of a JWT, and which part is secret?
2. What does the signature protect against? What does `exp` protect against?
3. Why do the services all need the **same** `JWT_SECRET` with HS256? What is the danger? (the brief mentions RS256 — explain the difference)
4. Why is a token with `sub: "admin"` refused? (hint: user ids are UUIDs)
5. 401 vs 403: give one example of each from this API.

Then in `test_m4_security.py` the table `OPERATIONS` lists the 8 operations and their allowed roles, and
`test_create_batch_without_a_token_is_401` is a **worked example**. Write the four loops (hints are in the file):
no token → 401 · bad tokens → 401 · wrong role → 403 · allowed role is never 401/403.

Check: `python -m pytest -q -m m4`. **Tip:** these tests need K3 done (the routes must exist) — until then you will see
"the application has NO such route".

---
## F1 · Create a batch (`TODO M2`) — Franck, ~3 h

1. `schemas.py` → `CreateBatchSchema`: three fields from the YAML (`course_code` pattern, `session_label` 1–60,
   `candidate_numbers` 1–200 items each matching `CANDIDATE_PATTERN`) and a `@field_validator("candidate_numbers")`
   refusing duplicates. Check: `pytest tests/test_units.py -m m2 -k schema`.
2. `store.py` → `create_batch`: follow the docstring literally: **batch id first, then one id per script, in the order given**;
   `created_at = stamp(self.clock())`; custodian = creator; `transfers = []`. Check: `-k store_create_batch`.
3. `api.py` → `createBatch`: decorator (201, `BatchSchema`), parameters (`payload`, `store`, `user: Officer`), body
   (`payload.model_dump(mode="json")` → `store.create_batch(..., created_by=user.id)`). Check: `pytest -m m2` (after K3).

Why `model_dump(mode="json")`? The store wants plain text and numbers, not pydantic objects or UUID objects.

## F2 · Custody transfers (`TODO M3`) — Franck, ~4 h

1. `CreateTransferSchema`: one `UUID` field.
2. `store.request_transfer`: four rules **in the order of the docstring**, then append a `pending` transfer.
   `store.accept_transfer`: two nested `for` loops to find the transfer, then three rules, then change the transfer **and**
   the batch's custodian in the same call. Check: `pytest tests/test_units.py -m m3`.
3. `api.py`: `ensure_valid_receiver` (ask the directory, translate the answers into 503 / 422), then `startTransfer`
   and `acceptTransfer`. Check: `pytest -m m3`.

Why is the receiver check in `api.py` and the other rules in the store? The store knows *data*; only the API layer has access to
the *directory* (the future Auth service). The store never calls another service.

---
## Final check
```
python -m pytest -q            # everything: units + API + security + contract
```
`test_contract.py` verifies that **the application serves exactly the 8 operations of the YAML**, with the right success codes and
response models. If it fails: compare http://127.0.0.1:8001/openapi.json with the YAML.
