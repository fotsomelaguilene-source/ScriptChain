# 07 · Working together: git, branches, pairing, review

## Git in 10 commands (first time with Kelly: do it together)
```
git init                               # once, in the root of the folder  (F)
git add -A && git commit -m "Starter"  # first snapshot
# create an empty repository on GitHub/GitLab, then:
git remote add origin <url> && git push -u origin main
# Kelly:
git clone <url> && cd ScriptChain_starter
# every task:
git checkout -b k1-response-models     # a branch = your own copy of the timeline
git add -A && git commit -m "K1: Script response models (7 classes)"
git push -u origin k1-response-models  # then open a "pull request" on the website, ask the partner to review
git checkout main && git pull          # after the merge, get the others' work
```
**Never** work on `main` directly. One branch per task (`k1-…`, `f2-…`). Commit small and often: "write 3 lines, run tests, commit".

If two people edited the same file you may get a **merge conflict**: git marks `<<<<<<<` / `>>>>>>>` in the file. Do not panic: decide together
which lines stay, delete the markers, run the tests, commit. *(To avoid it: K and F touch different regions — the TODO map gives each task its own functions.)*

## Commit messages
`<task id>: <what, in the imperative>` — e.g. `K2: list_batches sorts newest first`, `F3: replay idempotent bulk submissions`, `fix: 404 message names the batch`.

## Pair programming (use it for the hard 20%)
* **Driver** types, **navigator** thinks, reads the spec and watches for typos. Swap every 20–25 minutes.
* The navigator may only ask questions: *"which test will tell you?"*, *"what does the YAML say?"*, *"what does the error say, from the bottom?"*.
* If the driver is Kelly, Franck does **not** take the keyboard. That is the rule that makes it learning.

## Review checklist (use it for every pull request)
**Contract**
☐ Does the code match the YAML (names, types, required/optional, status codes)? ☐ Any hard-coded message that the docstring said to build from the error?
**Correctness**
☐ Rules are checked **in the order of the docstring**. ☐ Every refusal leaves the data **unchanged**. ☐ The store returns **copies**.
**Python**
☐ Parameters without default come before those with default. ☐ No typo in a `Field(...)` keyword (read the pytest *warnings*). ☐ No leftover `print`, no commented-out dead code.
**Security**
☐ Every operation depends on `AnyUser` or a role alias. ☐ No secret or token written in the code (the dev secret lives in `security.py` only).
**Tests**
☐ New behaviour has a test named after the rule. ☐ `make test` is green on the branch.

## A rhythm that works
Monday 20 min: choose the tasks of the week (the board in `TASKS.md`) · each work session starts with `git pull` and `make test` ·
each session ends with a commit and one line in the shared chat: *"done: K2 (unit tests green) · blocked: nothing"* ·
Friday 30 min: demo the week to each other with `/docs` and `make demo`.
