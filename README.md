# ScriptChain · Lab 2 starter (Script Service + Mark Service)

Group project, API Integration course. The lecturer asked us to build the project **the way Lab 2 was done**:
an OpenAPI contract, a starter full of TODOs, tests that check every response against the contract.
**You write the code. The tests tell you when it is right.** Guides explain how.

> New here? Read **`START_HERE.md`** (30 minutes), then **`TASKS.md`** to see who does what.

## What is in the folder

| Path | What |
|---|---|
| `START_HERE.md` | the first 30 minutes: install, run, see red, first commit |
| `TASKS.md` | **the task board**: Franck's and Kelly's tasks, order, estimates, pair sessions |
| `docs/00_decisions_and_open_questions.md` | decisions we took where the brief was open + questions for the lecturer |
| `docs/01_big_picture.md` | architecture of what we build, the layers, the journey of one request |
| `docs/02_python_fastapi_crash_course.md` | the Python/FastAPI you need, 12 lessons (for a beginner) |
| `docs/03_reading_the_openapi_file.md` | YAML → Python dictionary + a worksheet |
| `docs/04_script_service_guide.md` | step-by-step guide to every TODO of the Script service |
| `docs/05_mark_service_guide.md` | same for the Mark service |
| `docs/06_test_documentation.md` | how the tests work, how to read failures, rule → test table, full catalogue |
| `docs/07_teamwork_git.md` | git, branches, pair programming, review checklist |
| `docs/08_roadmap_next_steps.md` | Auth, AI helper, BFF, PostgreSQL, Docker, Kubernetes |
| `docs/09_debugging_cheatsheet.md` | symptom → cause → fix |
| `docs/REPORT_TEMPLATE.md` | the 1–2 page report |
| `services/script/` | **Script Service** (batches, scripts, custody transfers) — port 8001 |
| `services/mark/` | **Mark Service** (marks, adjustments, approval) — port 8002 |
| `tools/` | `make_token.py` (JWTs to try the API), `e2e_demo.py` (9 real HTTP steps) |

Inside each service:

```
openapi/…yaml   the CONTRACT (do not edit)          app/schemas.py   request + response models   YOU
data/seed.json  the records the service starts with   app/store.py     rules + data                YOU
app/api.py      the path operations                 YOU   app/ports.py   doors to other services   (K5 in Mark)
app/security.py JWT, roles       given              app/errors.py, clock.py, main.py       given
tests/          the judge (+ the tests Kelly writes: m4 security, m5 HTTP client)
```

## Commands (from the root)
```
python3 -m venv .venv && . .venv/bin/activate      # once  (Windows: .venv\Scripts\activate)
make install            # pinned dependencies
make test               # both services       make test-script M=m1   one milestone of one service
bash run_tests.sh       # one PASS/FAIL line per test + totals
make run-script         # Script service on http://127.0.0.1:8001  (docs on /docs)
make run-mark           # Mark service on http://127.0.0.1:8002
make demo               # end-to-end story through real HTTP (both services running)
make token              # list the seed users;  python tools/make_token.py officer  -> a JWT
make clean              # before zipping
```
No `make` on Windows? Run the commands inside the Makefile by hand (`cd services/script && python -m pytest -q`).

## Milestones (same idea as Lab 2)
* **M1** the read side — schemas, store reads, read routes · **M2** create (batch) / bulk submission (marks) ·
  **M3** custody transfers / moderation + approval · **M4** security tests (401/403) · **M5** HTTP client with timeouts and retries ·
  **contract** the app serves exactly the operations of the YAML.

At the start **almost every test is red**; that is normal. At the end both services are green (157 test cases) and `make demo` prints `[OK ]` nine times.

*All data is synthetic: fictional courses, candidate numbers and users.*
