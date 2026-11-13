# Report · Lab 2 applied to ScriptChain  *(copy this file to `REPORT.md`, 1–2 pages)*

**Team:** Franck · Kelly      **Date:**      **Services:** Script Service (8 endpoints) · Mark Service (8 endpoints)

## 1. What we built (5 lines)
Which services, how many endpoints, which rules (custodian, idempotency, locking), which tests are green (`make test` result: __ / __).

## 2. Design decisions and open questions
Pick the 5 decisions of `docs/00` you consider most important and defend each in two sentences (why 409 and not 422? why a replay before the
custodian check? why fail closed?). List the questions you put to the lecturer.

## 3. How the tests prove the rules
A table: rule → test name → what it checks. (Start from section 4 of `docs/06_test_documentation.md`, keep the 6 most important.)

## 4. Franck — what I built and what went wrong
Tasks F1–F4. One bug you found, its cause, and how the test led you to it.

## 5. Kelly — what I built and what I learned
Tasks K0–K6. The **security review** (answers to the 5 questions of `docs/04`, task K4) · the **timeout and retry choice** of K5
(value, reason, what happens to the user while retries run) · the spec worksheet of `docs/03`.

## 6. Limits and next steps
What is missing (Auth, AI helper, BFF, database, containers) and the order in which you will do it (`docs/08`).

## 7. Honest note on help
Say which parts you wrote alone, in pair, and where an AI assistant or the lectures helped you. You must be able to explain every line of code in
the oral.
