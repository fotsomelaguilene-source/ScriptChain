# TASKS · who does what, in which order

**Franck = F** (builds the harder parts, explains) · **Kelly = K** (learns step by step, strong in networking and security).
Rule: *Kelly writes real code from day 1, but every task has a test that tells her when she is done.*
Everyone works on **their own git branch** (`docs/07_teamwork_git.md`) and merges when the task's tests are green.

## Critical path (what blocks what)

```
 K0 setup+reading ──► K1 response models ──► K2 store reads ──► K3 read routes ═══► F1/F2 API tests, K4 security tests
 F0 setup ───────────► F1/F2 unit-level work (needs nothing from Kelly) ─────────────┘
```
The **read side (M1) is needed by almost every API test**, so it is Kelly's first mission, and Franck does the unit-level part of his
tasks in the meantime. Then both services' write tests turn green one by one.

## The board

Status legend: ☐ to do · ◐ in progress · ☑ done. Estimates are for a beginner (K) or a builder (F), in focused hours.

### Week 1 · Script Service

| ID | Owner | Task | Where | Done when | Est. | Status |
|---|---|---|---|---|---|---|
| F0 | F | Create the shared git repo, push this folder, invite K; install and run `make test` (all red) | root | both can run `make test` | 0.5 | ☐ |
| K0 | K | Setup + read `docs/00`, `01`, crash course `02` lessons 1–8, and answer the **spec worksheet** of `03` | `docs/` | worksheet answered in `REPORT.md` | 3 | ☐ |
| **P1** | F+K | **Pair session 1** (see below): K types, F navigates — do the first part of K1 together | `schemas.py` | `ScriptSchema` + `BatchSchema` done | 1.5 | ☐ |
| K1 | K | Script · 7 response models | `schemas.py` | unit tests `-m m1 -k schema` green | 2 | ☐ |
| K2 | K | Script · 5 store reads | `store.py` | unit tests `-m m1` green | 3 | ☐ |
| K3 | K | Script · 5 read routes | `api.py` | `pytest -m m1` green | 3 | ☐ |
| F1 | F | Script · create a batch (request model, `create_batch`, route) | `TODO M2` | `pytest -m m2` green | 3 | ☐ |
| F2 | F | Script · custody transfers (model, 2 store methods, helper, 2 routes) | `TODO M3` | `pytest -m m3` green | 4 | ☐ |
| K4 | K | Script · security tests **+ the security review** (5 questions of `04`) | `test_m4_security.py` | `pytest -m m4` green + answers in report | 3 | ☐ |
| R1 | F↔K | **Cross review**: each reads the other's pull request with the checklist of `07` | git | 2 reviews done | 1 | ☐ |

### Week 2 · Mark Service, then the two together

| ID | Owner | Task | Where | Done when | Est. | Status |
|---|---|---|---|---|---|---|
| K6 | K | Mark · read side: 8 response models, 5 store reads, 5 routes (**with less help**) | `TODO M1` | `pytest -m m1` green | 5 | ☐ |
| K5 | K | Mark · `HttpCustodianClient` + complete its 6 tests (timeouts, retries) | `ports.py`, `test_m5_http_client.py` | `pytest -m m5` green | 3 | ☐ |
| F3 | F | Mark · bulk submission: models, `submit_marks`, idempotent route | `TODO M2` | `pytest -m m2` green | 5 | ☐ |
| F4 | F | Mark · adjust + approve | `TODO M3` | `pytest -m m3` green | 3 | ☐ |
| K4b | K | Mark · security tests | `test_m4_security.py` | `pytest -m m4` green | 1 | ☐ |
| E2E | F+K | **Pair session 2**: run both services + `make demo`, then break things on purpose (stop the Script service, expired token…) and watch the answers | root | demo: 9 × `[OK ]` | 2 | ☐ |
| REP | F+K | Report: `docs/REPORT_TEMPLATE.md` → `REPORT.md` (each writes their own section) | root | 1–2 pages | 3 | ☐ |

### Afterwards (next starters — `docs/08_roadmap.md`)
Auth service · AI Moderation Helper · GraphQL BFF · PostgreSQL · Docker + Compose · kind/Minikube. **Kelly leads Docker/Compose and the
Kubernetes networking and probes** (her networking background), Franck leads the BFF and the databases.

---
## Why this split? (so you can explain it to the lecturer)
* **Kelly's tasks** go from *translating a spec into types* (K1) → *list/sort/filter code* (K2) → *wiring a function to a URL* (K3) → *security
  tests* (K4, her strength) → *networking code with retries* (K5, her strength) → *repeat the whole read side alone* (K6). Each step reuses the
  skill of the previous one and has an automatic judge.
* **Franck's tasks** are the ones with **business rules and several moving parts** (transfers, idempotency, locking): more design decisions
  and more ways to go wrong.
* Both see **all** the code in review: nobody owns a service alone, so both can answer in the oral.

## Pair session 1 (suggested script, 90 min)
1. (10 min) F shows the picture of `docs/01` — the layers and the journey of one request.
2. (10 min) Run `make test-script`: everything red. Open one failure together and read it from the bottom.
3. (40 min) **K drives (types), F navigates (asks questions, never types)**: write `ScriptSchema` and `BatchSchema` (K1, first two classes).
   F's only allowed moves: *"what does the YAML say?"*, *"which test will tell you?"*.
4. (20 min) K finishes the other classes alone while F watches; run the unit tests.
5. (10 min) First commit, push, F reviews with the checklist.

## Definition of done (for any task)
☐ the task's tests are green · ☐ the *other* tests that were green are still green · ☐ no `TODO` left in the code of the task · ☐ no hint comment
left behind that is now false · ☐ committed with a clear message · ☐ the partner read it.
