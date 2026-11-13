# 01 · The big picture: what this folder builds (and what it does not, yet)

## What "Lab 2 in our project" means

Lab 2 of the course gave you: **an OpenAPI file (the contract) + a starter with TODOs + tests that check every
response against the contract**. You wrote the code until the tests were green.
This folder does the same for **two real services of ScriptChain**:

| Service | Port | Owns | Endpoints |
|---|---|---|---|
| **Script Service** (`services/script`) | 8001 | batches, scripts, custody transfers | 8 |
| **Mark Service** (`services/mark`) | 8002 | marks, adjustments, approvals | 8 |

That is **16 endpoints**, all versioned `/v1`, each documented in OpenAPI 3 with one consistent error schema
(`{"detail": ...}`). The brief asks for at least 12.

### What is NOT in this folder yet (see `docs/08_roadmap.md`)
Auth service (login) · AI Moderation Helper · GraphQL BFF · PostgreSQL · Docker/Compose · Kubernetes.
They need these two services to be solid first. Everything here uses an **in-memory store** (a Python list), like Lab 2,
and **ports** (small interfaces) where a real database or another service will plug in later.

## The layers (read from top to bottom, one request = one trip down and back up)

```
 HTTP request  ──►  security.py      Who are you? (JWT)  -> 401 / 403
                    │
                    ▼
                    schemas.py        Is the body valid? (request models)  -> 422
                    │
                    ▼
                    api.py            The path operation: decorator + parameters + body.
                    │                  It only TALKS: to the store, and to a port (directory / custodian client).
                    ▼
                    store.py          The business rules and the data (list of dicts).
                    │                  Raises NotFound / Conflict / Unprocessable.
                    ▼
                    schemas.py        Response models: keep only the fields of the spec.
                    │
                    ▼
 HTTP response ◄──  main.py           ONE handler turns the errors into {"detail": "..."} + status code.
```

| File | Who writes it | Role |
|---|---|---|
| `openapi/*.yaml` | given (the contract) | what the API must do |
| `app/schemas.py` | **you** | request models + response models |
| `app/store.py` | **you** | rules + data |
| `app/api.py` | **you** | the path operations |
| `app/ports.py` | given (+ `HttpCustodianClient`: **you**) | doors to other services |
| `app/security.py`, `errors.py`, `clock.py`, `main.py` | given | JWT, errors, time/ids, app factory |
| `tests/` | given (+ security and client tests: **you**) | the judge |

## Journey of one request: `POST /v1/batches` by the exams officer

1. The client sends `Authorization: Bearer <jwt>` and a JSON body.
2. `security.require_roles("exams_officer")` verifies the signature and the expiry, reads `sub` and `role`.
   No token → **401**. Role `examiner` → **403**.
3. FastAPI validates the body against `CreateBatchSchema`. `course_code: "csc201"` → **422** with the exact
   location (`["body", "course_code"]`).
4. `create_batch()` in `api.py` calls `store.create_batch(...)`.
5. The store builds the batch and its scripts, takes an id from the **id factory** and a time from the **clock**.
6. `BatchSchema` filters the stored dict: `scripts` and `transfers` are inside the stored batch but **not** in the
   representation of the spec, so they are removed. Status **201**.

## Where the brief's measurable objectives are covered

| Objective of the brief | In this folder |
|---|---|
| ≥ 12 versioned `/v1` endpoints, OpenAPI 3 with examples, one error schema | 16 endpoints; both YAML files; `Error` schema; examples on the POST operations |
| Only the current custodian can enter marks (409/422) | `submit_marks` + tests in `test_m2_bulk.py` |
| Approved marks are locked (409) | `add_adjustment`, `submit_marks`, tests in `test_m3_moderation.py` |
| JWT + four roles, at least one 401/403 test per protected operation | `security.py` + `test_m4_security.py` (task K4: **Kelly writes it**) |
| Timeout path of service-to-service calls tested | `HttpCustodianClient` + `test_m5_http_client.py` (task K5) |
| GraphQL BFF, containers, Kubernetes | roadmap (next starters) |
