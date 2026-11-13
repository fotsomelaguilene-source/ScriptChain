# 00 · Decisions we made, and questions for the lecturer

The brief fixes the big rules. It leaves many details open. To be able to write a precise OpenAPI file and
precise tests, **we had to decide**. Every decision below is written in the OpenAPI files and in the tests.
If the lecturer answers differently, change the YAML first, then the tests, then the code (in that order).

> Exam tip: a good API design document shows *which decisions you took and why*. Keep this page in your report.

## Decisions taken in this starter

| # | Open point in the brief | Our decision | Where it lives |
|---|---|---|---|
| D1 | "creates script batches per course, with script counts" | The officer sends the **candidate numbers**; one script is created per number and `script_count` is their number. A script count alone would leave `Script.candidate_number` empty. | `CreateBatchSchema` |
| D2 | Who holds a new batch? | The **creating officer** is the first custodian. | `ScriptStore.create_batch` |
| D3 | Who can receive scripts? | An **active user with the role `examiner`** (the brief says "active examiner"). | `ensure_valid_receiver` |
| D4 | Not the custodian / not the receiver / key reused … which status? | **409 Conflict** = right request, wrong moment. **422** = the request itself is not acceptable. **403** is reserved for the *role*. | `app/errors.py` |
| D5 | Score range | **0 to 100**, decimals allowed, strings and booleans refused (`strict`). Marked "to confirm" in the brief. | `Score` in Mark `schemas.py` |
| D6 | Can a mark be entered twice? | **No.** A candidate gets one mark per batch; a correction goes through an *adjustment* ("marks are never overwritten"). | `MarkStore.submit_marks` |
| D7 | What is "pending moderation"? | Every mark batch whose status is **not approved** (`entered` or `in_moderation`). | `MarkStore.pending` |
| D8 | When does a batch become `in_moderation`? | At its **first adjustment**. | `MarkStore.add_adjustment` |
| D9 | Can the HOD approve a batch nobody moderated? | **Yes** (a moderator reviews only a *sample*). | `MarkStore.approve` |
| D10 | Idempotency scope | The key is remembered **with a fingerprint** of (batch, user, body). Same key + same request → first answer replayed (even if the Script service is down); same key + different request → 422. | `submit_marks` in Mark `api.py` |
| D11 | Mark does not read `script_db`, so what about `script_id` of the class diagram? | Dropped from the mark record in v1.0: Mark only knows `candidate_number`. | Mark spec |
| D12 | User ids | Always **UUID strings** (the `sub` claim). A token whose `sub` is not a UUID is a 401. | `security.py` |
| D13 | Pagination | `limit` 1–100 (default 10), `offset` ≥ 0 on the collections. | both specs |
| D14 | Authentication in "Lab 2" | The brief wants JWT + four roles on all writes. We apply it to **every** operation of both services (reads need any valid token). Login and the Auth service come later (roadmap). Tokens are made by `tools/make_token.py` and by the tests. | `security.py` |
| D15 | Rejecting a transfer | The model has `REJECTED` but the brief lists no endpoint for it. **Not implemented in v1.0.** | Script spec |

## Questions to put to the lecturer (copy them in the report)

1. Is a **fourth and fifth container** (Auth service and AI Moderation Helper) welcome next to the three required?
2. Is the score range really 0–100? Are decimals (62.5) allowed?
3. Must the receiver of a transfer always be an **examiner**, or can an examiner hand scripts to a moderator?
4. Should there be a **reject transfer** endpoint? (the enum has REJECTED)
5. Should the HOD be allowed to approve a batch **without any moderation**?
6. Does "at least 12 endpoints across the two domain services" count the health probes? (we assume **no**: we have 16)
7. For the denied-access tests: is 403 expected for a wrong **role** and 409/422 for the **custodian** rule? (we assume yes)

> Note: the pasted brief stopped in the middle of section 7 (Auth service); sections 8–11 (including the open
> questions list) were not in what we received. If they contain other requirements, tell us and we adapt.
