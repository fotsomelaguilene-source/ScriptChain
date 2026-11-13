# START HERE · the first 30 minutes

## 1. Install (10 min)
Python 3.12 or 3.13 is needed (`python3 --version`).
```
cd ScriptChain_starter
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. See it all red (5 min)
```
make test-script
```
Dozens of failures: **good**. Look at the messages: `reached TODO M2: create_batch -- ...` or `the application has NO such route`.
Each message tells you *where* the missing code is. Your job is to make them green, one by one.

## 3. Meet the API (5 min) — it already starts, even with TODOs
```
make run-script                  # leave it running; open http://127.0.0.1:8001/docs
```
In another terminal: `python tools/make_token.py officer` → copy the token → in `/docs` click **Authorize**, paste it.
Only a few operations exist yet (the stubs have no decorator): that is the work to do. Stop the server with Ctrl+C.

## 4. Read, in this order (the rest of the first day)
1. `docs/01_big_picture.md` — 10 min, one picture.
2. `docs/00_decisions_and_open_questions.md` — 10 min.
3. **Kelly:** `docs/02_python_fastapi_crash_course.md` (lessons 1–8) and the worksheet of `docs/03`.
   **Franck:** `docs/04_script_service_guide.md` and the YAML of the Script service.

## 5. Then
Open **`TASKS.md`**, take your first task, work with the loop: *write a little → run the tests → read the first failure from the bottom → fix → commit*.

## If something does not work
* `ModuleNotFoundError` → the virtual environment is not active (step 1).
* `make: command not found` (Windows) → run the commands of the Makefile by hand.
* Port already in use → `PORT=8011 python -m app` (inside the service folder).
* `docs/09_debugging_cheatsheet.md` has the usual suspects.
