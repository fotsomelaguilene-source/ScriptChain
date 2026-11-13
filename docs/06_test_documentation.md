# 06 · Test documentation

> For the report and the oral: *what is tested, how, and why you can trust the result.*

## 1. How the tests work

| Idea | What it means for you |
|---|---|
| **In-process** | The API runs inside the test (`TestClient`): no network, no port, no server to start. Each test gets a **fresh application** with a fresh store, so tests never disturb each other. |
| **Deterministic time and ids** | The store receives a *clock* and an *id factory* (`app/clock.py`). In tests the clock starts at `2026-11-02T09:00:00Z` and advances one minute per reading; ids are `uuid5("new-1")`, `uuid5("new-2")`… So a test can say "the new batch must have id `NEW_IDS[0]` and `created_at` `2026-11-02T09:00:00Z`" — impossible with real clocks and random ids. |
| **Spec-conformance on EVERY response** | The test client (`SpecClient` in `tests/conftest.py`) checks each response against the **OpenAPI file**: the status code must be *documented* for that operation and the JSON body must *validate* against the documented schema (types, required fields, patterns, `Z` timestamps). A missing field or an undocumented 500 fails *any* test that touches it. |
| **Seed data** | `data/seed.json` holds known records (3 batches / 3 mark batches), so read tests need nothing else. |
| **Fakes instead of other services** | The Script service never calls Auth, and the Mark service never calls Script, during the tests. A **fake** plays the other side: `DownDirectory` (Auth is down), `FakeCustodians` (who holds each batch; `.down = True`; `.calls` records every question) and `httpx.MockTransport` (a pretend network for `HttpCustodianClient`). |
| **Three kinds of test** | **Unit** (`test_units.py`): one schema or one store method, no HTTP — fastest feedback. **API** (`test_m1…m5`): the whole path operation, through HTTP. **Contract** (`test_contract.py`): the app serves exactly the operations of the YAML. |

## 2. Running them
```
make test                        both services              bash run_tests.sh   one PASS/FAIL line per test + total
make test-script M=m1            one milestone              python -m pytest -q -x --tb=short -k "name"   (inside services/<x>)
```
Markers: `m1` reads · `m2` create / bulk · `m3` transfers / moderation · `m4` security · `m5` HTTP client · `contract`.

## 3. How to read a failure
| You see | It means | Look at |
|---|---|---|
| `reached TODO M2: create_batch -- ...` | the test hit code you have not written yet | the TODO named in the message |
| `the application has NO such route -- did you write the @router.xxx(...) decorator?` | a path operation is still a stub | `app/api.py` |
| `answered 500 / 404 ..., a status code the specification does not document` | the status is wrong for this operation | the `responses:` of the operation in the YAML |
| `the body does not match the specification: ... is a required property` / `... is not of type 'integer'` | a field is missing or of the wrong type in the answer | the **response model** in `schemas.py` |
| `assert set(batch) == BATCH_KEYS` fails (extra keys such as `scripts`) | the answer shows fields the spec does not show | the **response model**: do not declare them |
| `ResponseValidationError ... Input should be a valid dictionary` | the route returned a list instead of an object (or a wrong shape) | the `return` of the route |
| `assert 404 == 422` | the status is wrong | the parameter types (`UUID`?) / the rule order |
| `Failed: DID NOT RAISE` | a validation rule is missing (or misspelled) | `Field(...)` keywords — a typo is silently ignored! |
| `assert {'detail': 'Order Not found'} == {...}` | a hard-coded message | raise the error with the message the docstring asks for |
| `TODO K4/K5: ...` | a test that **you** must write | the file named in the message |

## 4. Business rules of the brief → the tests that prove them

| Rule (brief or decision) | Tests |
|---|---|
| **Only the current custodian can enter marks** (409) | Mark `test_only_the_current_custodian_can_enter_marks` · `test_the_caller_token_is_forwarded_to_the_script_service` |
| **If the Script service does not answer, Mark fails closed** (503, nothing saved) | Mark `test_when_the_script_service_is_down_marks_are_refused_with_503` · `test_m5_http_client.py` (timeout, retries) |
| **Approved marks are locked** (409) | Mark `test_approved_marks_cannot_be_adjusted` · `test_approved_marks_are_locked_even_for_the_custodian` · `test_approval_locks_the_marks` |
| **Bulk submission is idempotent** | Mark `test_a_retry_with_the_same_key_does_not_save_twice` · `test_a_retry_still_works_while_the_script_service_is_down` · `test_the_same_key_for_a_different_request_is_422` |
| **Marks are never overwritten** | Mark `test_a_mark_that_was_already_entered_is_never_overwritten` · `test_store_add_adjustment` |
| **An adjustment needs the moderator role and a non-empty reason** | Mark `test_an_adjustment_needs_a_valid_score_and_a_real_reason` · `test_wrong_role_is_403_…` |
| **Only the HOD can approve; once** | Mark `test_the_hod_approves_a_batch` · `test_a_batch_cannot_be_approved_twice` |
| **Only the current custodian can start a transfer** | Script `test_only_the_current_custodian_can_start_a_transfer` |
| **Only the named receiver can accept it** | Script `test_only_the_named_receiver_can_accept` |
| **At most one pending transfer per batch** | Script `test_a_batch_has_at_most_one_pending_transfer` |
| **A resolved transfer is never edited; history is append-only** | Script `test_accept_moves_the_custody_to_the_receiver` (history kept) · `test_a_resolved_transfer_cannot_be_accepted_again` |
| **The receiver must exist, be active, be an examiner; Auth down → 503** | Script `test_the_receiver_must_be_an_active_examiner` · `test_when_auth_is_down_the_transfer_fails_closed_with_503` |
| **JWT: a denied-access test for every protected operation (401/403)** | `test_m4_security.py` in both services (**written by Kelly**) |
| **The API serves exactly what the specification says** | `test_contract.py` + the conformance check inside every API test |

## 5. How to write a new test (template)
```python
def test_<one rule, in a sentence>(api):
    # arrange: the state you need (seed data, or create it through the API)
    created = api.post("/v1/batches", as_=OFFICER, json=new_batch()).json()
    # act: ONE call that is the point of the test
    response = api.post("/v1/batches/{batch_id}/transfers", as_=EXAMINER_TWO, batch_id=created["id"],
                        json={"to_user_id": EXAMINER_1_ID})
    # assert: the status code, then the body or the side effect (is anything stored?)
    assert response.status_code == 409
```
* Name the **rule**, not the function: `test_only_the_current_custodian_can_start_a_transfer`.
* One rule per test. Test the **refusal** *and* that **nothing was changed** afterwards.
* `as_=OFFICER` sends a valid token of that actor; `token="..."` sends exactly that text; neither sends no header.
* Path templates keep their `{braces}`: `api.get("/v1/batches/{batch_id}", as_=OFFICER, batch_id=...)` — that is how the response is matched to the right operation of the YAML.

## 6. Catalogue (generated from the test files)

Each row is a test function; **Cases** counts the parametrized variants. Tests marked `TODO K4/K5` are written by Kelly (the loops and the client tests).

### Script service  (`services/script/tests/`)

| Milestone | File | Test | What it proves | Cases |
|---|---|---|---|---|
| `contract` | `test_contract.py` | `test_every_operation_of_the_spec_is_served_and_nothing_else` | Every operation of the spec is served and nothing else | 1 |
| `m1` | `test_m1_reads.py` | `test_list_returns_the_three_seed_batches_newest_first` | List returns the three seed batches newest first | 1 |
| `m1` | `test_m1_reads.py` | `test_course_filter` | Course filter | 1 |
| `m1` | `test_m1_reads.py` | `test_limit_and_offset` | Limit and offset | 1 |
| `m1` | `test_m1_reads.py` | `test_invalid_query_parameters_are_rejected_with_422` | Invalid query parameters are rejected with 422 | 1 |
| `m1` | `test_m1_reads.py` | `test_get_batch_returns_the_csc201_batch` | Get batch returns the csc201 batch | 1 |
| `m1` | `test_m1_reads.py` | `test_batches_are_shown_without_their_internal_lists` | The stored batch holds 'scripts' and 'transfers'; the spec's BatchSchema does not show them. | 1 |
| `m1` | `test_m1_reads.py` | `test_unknown_batch_is_404_with_its_id_in_the_detail` | Unknown batch is 404 with its id in the detail | 1 |
| `m1` | `test_m1_reads.py` | `test_malformed_batch_id_is_422` | Malformed batch id is 422 | 1 |
| `m1` | `test_m1_reads.py` | `test_scripts_are_ordered_by_candidate_number_and_paged` | Scripts are ordered by candidate number and paged | 1 |
| `m1` | `test_m1_reads.py` | `test_custodian_of_a_batch` | Custodian of a batch | 1 |
| `m1` | `test_m1_reads.py` | `test_custody_history` | Custody history | 1 |
| `m1` | `test_m1_reads.py` | `test_optional_fields_are_omitted_never_null` | A pending transfer has no responded_at: the key must be ABSENT, not null. | 1 |
| `m2` | `test_m2_create.py` | `test_create_batch_answers_201_with_the_representation` | Create batch answers 201 with the representation | 1 |
| `m2` | `test_m2_create.py` | `test_one_script_is_created_per_candidate_number` | One script is created per candidate number | 1 |
| `m2` | `test_m2_create.py` | `test_new_batches_are_listed_first_and_get_ids_in_order` | New batches are listed first and get ids in order | 1 |
| `m2` | `test_m2_create.py` | `test_invalid_batches_are_rejected_with_422_and_nothing_is_stored` | Invalid batches are rejected with 422 and nothing is stored | 9 |
| `m3` | `test_m3_transfers.py` | `test_start_transfer_creates_a_pending_transfer` | Start transfer creates a pending transfer | 1 |
| `m3` | `test_m3_transfers.py` | `test_only_the_current_custodian_can_start_a_transfer` | Only the current custodian can start a transfer | 1 |
| `m3` | `test_m3_transfers.py` | `test_a_batch_has_at_most_one_pending_transfer` | A batch has at most one pending transfer | 1 |
| `m3` | `test_m3_transfers.py` | `test_a_batch_cannot_be_handed_to_its_own_custodian` | A batch cannot be handed to its own custodian | 1 |
| `m3` | `test_m3_transfers.py` | `test_the_receiver_must_be_an_active_examiner` | The receiver must be an active examiner | 3 |
| `m3` | `test_m3_transfers.py` | `test_when_auth_is_down_the_transfer_fails_closed_with_503` | When auth is down the transfer fails closed with 503 | 1 |
| `m3` | `test_m3_transfers.py` | `test_start_transfer_on_an_unknown_batch_is_404_and_a_malformed_body_is_422` | Start transfer on an unknown batch is 404 and a malformed body is 422 | 1 |
| `m3` | `test_m3_transfers.py` | `test_accept_moves_the_custody_to_the_receiver` | Accept moves the custody to the receiver | 1 |
| `m3` | `test_m3_transfers.py` | `test_only_the_named_receiver_can_accept` | Only the named receiver can accept | 1 |
| `m3` | `test_m3_transfers.py` | `test_a_resolved_transfer_cannot_be_accepted_again` | A resolved transfer cannot be accepted again | 1 |
| `m3` | `test_m3_transfers.py` | `test_accept_an_unknown_transfer_is_404_and_a_malformed_id_is_422` | Accept an unknown transfer is 404 and a malformed id is 422 | 1 |
| `m3` | `test_m3_transfers.py` | `test_full_custody_chain_officer_to_examiner_to_examiner` | Full custody chain officer to examiner to examiner | 1 |
| `m4` | `test_m4_security.py` | `test_create_batch_without_a_token_is_401` | WORKED EXAMPLE (given). Study it: the other tests are the same idea, in a loop. | 1 |
| `m4` | `test_m4_security.py` | `test_no_token_is_401_for_every_operation` | Loop over OPERATIONS: call each one with NO token and expect 401. | 1 |
| `m4` | `test_m4_security.py` | `test_bad_tokens_are_401` | A token that is present but not acceptable must be refused with 401 (try it on getBatches). | 5 |
| `m4` | `test_m4_security.py` | `test_wrong_role_is_403_for_every_protected_write` | For every operation, every role that is NOT allowed must get 403. | 1 |
| `m4` | `test_m4_security.py` | `test_every_allowed_role_gets_past_the_security_check` | The other side of the coin: an ALLOWED role must never get 401 or 403 (404/409/422 are fine). | 1 |
| `m1` | `test_units.py` | `test_batch_schema_hides_the_scripts_and_the_transfers` | Batch schema hides the scripts and the transfers | 1 |
| `m1` | `test_units.py` | `test_transfer_schema_omits_responded_at_while_pending` | Transfer schema omits responded at while pending | 1 |
| `m1` | `test_units.py` | `test_the_list_schemas_wrap_their_items` | The list schemas wrap their items | 1 |
| `m1` | `test_units.py` | `test_response_models_check_the_types` | Response models check the types | 1 |
| `m1` | `test_units.py` | `test_store_list_batches_newest_first_filtered_and_sliced` | Store list batches newest first filtered and sliced | 1 |
| `m1` | `test_units.py` | `test_store_hands_out_copies_not_the_stored_records` | Store hands out copies not the stored records | 1 |
| `m1` | `test_units.py` | `test_store_get_batch_scripts_custodian_and_history` | Store get batch scripts custodian and history | 1 |
| `m2` | `test_units.py` | `test_create_batch_schema_accepts_a_valid_payload` | Create batch schema accepts a valid payload | 1 |
| `m2` | `test_units.py` | `test_create_batch_schema_refuses_invalid_payloads` | Create batch schema refuses invalid payloads | 8 |
| `m2` | `test_units.py` | `test_create_batch_schema_requires_its_three_fields` | Create batch schema requires its three fields | 1 |
| `m2` | `test_units.py` | `test_store_create_batch` | Store create batch | 1 |
| `m3` | `test_units.py` | `test_create_transfer_schema_needs_a_uuid` | Create transfer schema needs a uuid | 1 |
| `m3` | `test_units.py` | `test_store_request_transfer` | Store request transfer | 1 |
| `m3` | `test_units.py` | `test_store_request_transfer_rules` | Store request transfer rules | 1 |
| `m3` | `test_units.py` | `test_store_accept_transfer` | Store accept transfer | 1 |
| `m3` | `test_units.py` | `test_store_accept_transfer_rules` | Store accept transfer rules | 1 |

**71 test cases** in the Script service.

### Mark service  (`services/mark/tests/`)

| Milestone | File | Test | What it proves | Cases |
|---|---|---|---|---|
| `contract` | `test_contract.py` | `test_every_operation_of_the_spec_is_served_and_nothing_else` | Every operation of the spec is served and nothing else | 1 |
| `m1` | `test_m1_reads.py` | `test_marks_of_a_batch_are_ordered_by_candidate_number` | Marks of a batch are ordered by candidate number | 1 |
| `m1` | `test_m1_reads.py` | `test_marks_limit_and_offset` | Marks limit and offset | 1 |
| `m1` | `test_m1_reads.py` | `test_marks_are_shown_without_their_internal_adjustment_list` | The stored mark holds a list 'adjustments'; the spec's MarkSchema does not show it. | 1 |
| `m1` | `test_m1_reads.py` | `test_a_batch_without_marks_is_404` | A batch without marks is 404 | 1 |
| `m1` | `test_m1_reads.py` | `test_get_mark_shows_the_original_and_the_current_score` | Get mark shows the original and the current score | 1 |
| `m1` | `test_m1_reads.py` | `test_unknown_mark_is_404_and_malformed_id_is_422` | Unknown mark is 404 and malformed id is 422 | 1 |
| `m1` | `test_m1_reads.py` | `test_change_history_of_a_mark` | Change history of a mark | 1 |
| `m1` | `test_m1_reads.py` | `test_pending_lists_the_batches_that_are_not_approved_newest_first` | Pending lists the batches that are not approved newest first | 1 |
| `m1` | `test_m1_reads.py` | `test_get_approval` | Get approval | 1 |
| `m1` | `test_m1_reads.py` | `test_a_batch_that_is_not_approved_has_no_approval_record` | A batch that is not approved has no approval record | 1 |
| `m2` | `test_m2_bulk.py` | `test_the_custodian_saves_marks` | The custodian saves marks | 1 |
| `m2` | `test_m2_bulk.py` | `test_the_caller_token_is_forwarded_to_the_script_service` | The caller token is forwarded to the script service | 1 |
| `m2` | `test_m2_bulk.py` | `test_only_the_current_custodian_can_enter_marks` | Only the current custodian can enter marks | 1 |
| `m2` | `test_m2_bulk.py` | `test_when_the_script_service_is_down_marks_are_refused_with_503` | When the script service is down marks are refused with 503 | 1 |
| `m2` | `test_m2_bulk.py` | `test_a_batch_unknown_to_the_script_service_is_404` | A batch unknown to the script service is 404 | 1 |
| `m2` | `test_m2_bulk.py` | `test_the_idempotency_key_header_is_required` | The idempotency key header is required | 1 |
| `m2` | `test_m2_bulk.py` | `test_invalid_marks_are_rejected_with_422_and_nothing_is_saved` | Invalid marks are rejected with 422 and nothing is saved | 9 |
| `m2` | `test_m2_bulk.py` | `test_a_retry_with_the_same_key_does_not_save_twice` | A retry with the same key does not save twice | 1 |
| `m2` | `test_m2_bulk.py` | `test_a_retry_still_works_while_the_script_service_is_down` | A retry still works while the script service is down | 1 |
| `m2` | `test_m2_bulk.py` | `test_the_same_key_for_a_different_request_is_422` | The same key for a different request is 422 | 1 |
| `m2` | `test_m2_bulk.py` | `test_a_mark_that_was_already_entered_is_never_overwritten` | A mark that was already entered is never overwritten | 1 |
| `m2` | `test_m2_bulk.py` | `test_more_marks_can_be_added_for_other_candidates` | More marks can be added for other candidates | 1 |
| `m2` | `test_m2_bulk.py` | `test_approved_marks_are_locked_even_for_the_custodian` | Approved marks are locked even for the custodian | 1 |
| `m3` | `test_m3_moderation.py` | `test_a_moderator_adjusts_a_mark_with_a_reason` | A moderator adjusts a mark with a reason | 1 |
| `m3` | `test_m3_moderation.py` | `test_adjustments_pile_up_and_each_remembers_the_score_before_it` | Adjustments pile up and each remembers the score before it | 1 |
| `m3` | `test_m3_moderation.py` | `test_the_first_adjustment_moves_the_batch_to_in_moderation` | The first adjustment moves the batch to in moderation | 1 |
| `m3` | `test_m3_moderation.py` | `test_an_adjustment_needs_a_valid_score_and_a_real_reason` | An adjustment needs a valid score and a real reason | 6 |
| `m3` | `test_m3_moderation.py` | `test_adjust_an_unknown_mark_is_404` | Adjust an unknown mark is 404 | 1 |
| `m3` | `test_m3_moderation.py` | `test_approved_marks_cannot_be_adjusted` | Approved marks cannot be adjusted | 1 |
| `m3` | `test_m3_moderation.py` | `test_the_hod_approves_a_batch` | The hod approves a batch | 1 |
| `m3` | `test_m3_moderation.py` | `test_approval_locks_the_marks` | Approval locks the marks | 1 |
| `m3` | `test_m3_moderation.py` | `test_a_batch_cannot_be_approved_twice` | A batch cannot be approved twice | 1 |
| `m3` | `test_m3_moderation.py` | `test_a_batch_without_marks_cannot_be_approved` | A batch without marks cannot be approved | 1 |
| `m3` | `test_m3_moderation.py` | `test_full_marking_workflow` | Full marking workflow | 1 |
| `m4` | `test_m4_security.py` | `test_approve_without_a_token_is_401` | WORKED EXAMPLE (given). Study it: the other tests are the same idea, in a loop. | 1 |
| `m4` | `test_m4_security.py` | `test_no_token_is_401_for_every_operation` | Loop over OPERATIONS: call each one with NO token and expect 401. | 1 |
| `m4` | `test_m4_security.py` | `test_bad_tokens_are_401` | A token that is present but not acceptable must be refused with 401 (try it on getMarks). | 5 |
| `m4` | `test_m4_security.py` | `test_wrong_role_is_403_for_every_protected_operation` | For every operation, every role that is NOT allowed must get 403. | 1 |
| `m4` | `test_m4_security.py` | `test_every_allowed_role_gets_past_the_security_check` | The other side of the coin: an ALLOWED role must never get 401 or 403 (404/409/422 are fine). | 1 |
| `m5` | `test_m5_http_client.py` | `test_a_200_answer_gives_the_custodian_id_and_forwards_the_token` | WORKED EXAMPLE (given): read it line by line before writing the others. | 1 |
| `m5` | `test_m5_http_client.py` | `test_a_404_means_the_batch_is_unknown_and_is_not_retried` | A 404 means the batch is unknown and is not retried | 1 |
| `m5` | `test_m5_http_client.py` | `test_a_timeout_is_retried_then_fails_closed` | A timeout is retried then fails closed | 1 |
| `m5` | `test_m5_http_client.py` | `test_a_connection_error_is_retried_then_fails_closed` | A connection error is retried then fails closed | 1 |
| `m5` | `test_m5_http_client.py` | `test_a_server_error_then_a_good_answer_succeeds_on_the_retry` | A server error then a good answer succeeds on the retry | 1 |
| `m5` | `test_m5_http_client.py` | `test_a_server_that_keeps_failing_fails_closed_after_all_the_attempts` | A server that keeps failing fails closed after all the attempts | 1 |
| `m5` | `test_m5_http_client.py` | `test_a_refusal_is_not_retried_and_is_treated_as_unavailable` | A refusal is not retried and is treated as unavailable | 2 |
| `m1` | `test_units.py` | `test_mark_schema_hides_the_adjustment_list` | Mark schema hides the adjustment list | 1 |
| `m1` | `test_units.py` | `test_adjustment_approval_and_pending_schemas` | Adjustment approval and pending schemas | 1 |
| `m1` | `test_units.py` | `test_response_models_check_the_types` | Response models check the types | 1 |
| `m1` | `test_units.py` | `test_store_marks_are_sorted_sliced_and_copied` | Store marks are sorted sliced and copied | 1 |
| `m1` | `test_units.py` | `test_store_adjustments_pending_and_approval` | Store adjustments pending and approval | 1 |
| `m2` | `test_units.py` | `test_bulk_schema_accepts_valid_marks` | Bulk schema accepts valid marks | 1 |
| `m2` | `test_units.py` | `test_bulk_schema_refuses_invalid_marks` | Bulk schema refuses invalid marks | 9 |
| `m2` | `test_units.py` | `test_mark_entry_schema` | Mark entry schema | 1 |
| `m2` | `test_units.py` | `test_store_submit_marks_creates_the_batch_and_the_marks` | Store submit marks creates the batch and the marks | 1 |
| `m2` | `test_units.py` | `test_store_submit_marks_rules` | Store submit marks rules | 1 |
| `m3` | `test_units.py` | `test_adjustment_request_schema` | Adjustment request schema | 1 |
| `m3` | `test_units.py` | `test_store_add_adjustment` | Store add adjustment | 1 |
| `m3` | `test_units.py` | `test_store_approve` | Store approve | 1 |

**86 test cases** in the Mark service.

