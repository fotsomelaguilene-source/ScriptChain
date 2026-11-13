# 09 · Debugging cheat-sheet (every item below happened in a real Lab 2)

| Symptom | Real cause | Fix |
|---|---|---|
| All list tests crash with `ResponseValidationError ... Input should be a valid dictionary` | the route **returned a bare list**; the spec says an object `{"batches": [...]}` | `return {"batches": store.list_batches(...)}` |
| `SyntaxError: non-default argument follows default argument` | a parameter with a default came before one without | put `store: Store`, path values and body **first**, `limit: ... = 10` **last** |
| (workaround that hides it) `store: Store = Store` | the default `Store` is the *type*, not an instance | never; reorder the parameters instead |
| `quantity: 0` / `score: 101` accepted | **typo in a `Field` keyword** (`e=1` instead of `ge=1`, `max_lenth`) — pydantic only prints a *deprecation warning* | read the warnings of pytest; the rule must exist: `Field(ge=1, le=100)` |
| `/v1/batches/not-a-uuid` gives 404 instead of 422 | path parameter typed `object` or `str` | `batch_id: UUID` |
| 404 message is "Order Not found" instead of naming the id | message hard-coded | `raise NotFound(f"Batch {batch_id} not found")` / use the message the docstring gives |
| `KeyError: 'refund'` instead of `ValueError` | `ACTIONS[action]` on an unknown key | `if action not in ACTIONS: raise ValueError(...)` |
| a bare `except:` swallows everything | too broad: it hides real bugs | `except ValueError:` (the precise error) |
| response shows `scripts` and `transfers` inside a batch | the response model declares them, or still has the `extra="allow"` placeholder | declare only the spec's fields |
| optional field shows `null` in the JSON | `exclude_none` missing or the field is not `X \| None = None` | `response_model_exclude_none=True` + `datetime \| None = None` |
| a created batch has a random id in the test | you called `uuid.uuid4()` yourself | use `self.new_id()` and `self.clock()` — never the real ones in the store |
| the test says "NO such route" | decorator missing, wrong method or wrong path (a typo in `/v1/batchs`) | compare with the `paths:` of the YAML |
| 401 instead of 200 in a test | the route does not depend on `AnyUser`/a role alias, or you sent no token | add `user: AnyUser`; in a test use `as_=OFFICER` |
| 403 instead of 201 | wrong role alias on the route (`Examiner` instead of `Officer`) | check the role table in the spec |
| the store is modified through a returned dict | you returned the stored record, not a copy | `copy.deepcopy(...)` |
| `RuntimeWarning`/`InsecureKeyLengthWarning` | JWT secret shorter than 32 bytes | keep the long dev secret; use ≥ 32 characters in real life |
| the demo says `503` at step "submits marks" | Script service not running on 8001, or `HttpCustodianClient` unfinished | `make run-script`; finish K5 |

## A 5-step method when you are stuck
1. **Read the last line** of the error (pytest prints your files; ignore `site-packages` lines).
2. **Run only that test**: `python -m pytest -q -x --tb=short -k <part of its name>`.
3. **Print what you really have**: `print(response.json())` in the test, or `print(result)` in the function (remove it afterwards).
4. **Compare with the YAML**, line by line — status code, field names, required/optional.
5. Explain the problem **out loud to your partner** (rubber-duck): half of the bugs are found in step 5.
