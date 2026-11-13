# 02 · Crash course: the Python you need, in 12 short lessons

Written for someone who knows networks and security but has **never written a web API**. Every lesson uses a
*library* example (books), never ScriptChain code, so you still have to write the real code yourself.
Type each example in a scratch file (`python scratch.py`) — do not just read.

> Rule for the whole project: **run the tests after every small change.** Small steps, green tests.

---
## Lesson 1 · Data: dict and list
```python
book = {"id": "b1", "title": "Une vie de boy", "year": 1956}      # a dict: key -> value
print(book["title"])                                              # read
book["year"] = 1957                                               # change
shelf = [book, {"id": "b2", "title": "Mission terminée", "year": 1957}]   # a list of dicts
print(len(shelf), shelf[0]["id"])
```
In ScriptChain a **record** is a dict and a **table** is a list of dicts. `data/seed.json` is exactly that.

## Lesson 2 · Functions and type hints
```python
def title_of(book: dict) -> str:       # `: dict` and `-> str` are hints for humans and tools
    return book["title"]
```
A function **returns** a value (`return`) or raises an error. No `return` = it returns `None`.

## Lesson 3 · Sorting, filtering, slicing  *(you will use these ALL the time)*
```python
newest_first = sorted(shelf, key=lambda b: b["year"], reverse=True)    # sort by one field
recent = [b for b in shelf if b["year"] >= 1957]                       # list comprehension = filter
page = shelf[2:5]                                                      # slice: items 2,3,4
offset, limit = 10, 5
page = shelf[offset: offset + limit]                                   # pagination = one slice
```
`lambda b: b["year"]` is a tiny nameless function: "given b, give me b's year".

## Lesson 4 · Copies: why the store uses `copy.deepcopy`
```python
import copy
a = {"tags": ["x"]}
b = a                      # NOT a copy: same object
c = copy.deepcopy(a)       # a real, independent copy
b["tags"].append("y")      # a changed too!   c did not.
```
The store hands out **copies**, so callers can never change the stored data by accident.

## Lesson 5 · Classes and methods
```python
class Shelf:
    def __init__(self, books):          # runs when you write Shelf([...])
        self._books = books             # `self` = this object; the underscore means "private"
    def count(self) -> int:
        return len(self._books)
    def find(self, book_id):
        for book in self._books:
            if book["id"] == str(book_id):
                return book
        raise LookupError(book_id)      # see lesson 6
```
`ScriptStore` and `MarkStore` are classes like this. A **method** is a function inside a class; it receives `self` first.

## Lesson 6 · Errors: raise and catch
```python
try:
    book = shelf.find("zz")
except LookupError:
    print("not found")
```
In the store you **raise** `NotFound(...)`, `Conflict(...)`, `Unprocessable(...)` (see `app/errors.py`). You never write a
status code by hand: one handler in `main.py` turns each error into the HTTP answer.
*409 = right request, wrong moment. 422 = the request itself is unacceptable.*

## Lesson 7 · Pydantic models: validation for free
```python
from pydantic import BaseModel, Field

class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)        # text of 1..80 characters
    isbn: str = Field(pattern=r"^[0-9]{10}$")               # regular expression
    pages: int = Field(ge=1, le=2000)                        # ge = "greater or equal", le = "less or equal"
    subtitle: str | None = None                              # OPTIONAL: may be missing
```
`BookIn.model_validate({...})` raises `ValidationError` if the data is wrong. FastAPI does this for you on every request
and answers **422**.
⚠️ **A typo in a `Field(...)` keyword is NOT an error**: `Field(e=1)` instead of `ge=1` is silently accepted and the
rule does not exist. Read pydantic's *warnings* — they tell you. (This is the #1 bug of Lab 2.)

## Lesson 8 · A FastAPI path operation (the four parts)
```python
@router.get("/books/{book_id}", status_code=200, response_model=BookOut)    # 1. DECORATOR: method, path, code, answer shape
def get_book(book_id: UUID, store: Store):                                    # 2. PARAMETERS: path value, collaborators
    return store.get(book_id)                                                 # 3. BODY: talk to the store, return the result
```
* `{book_id}` in the path + `book_id: UUID` in the parameters → FastAPI checks it is a UUID (else **422**).
* Query parameters: `limit: Annotated[int, Query(ge=1, le=100)] = 10` (`?limit=20`).
* Body: a parameter typed with a pydantic model (`payload: BookIn`).
* ⚠️ **Python rule**: parameters **without** a default come **before** parameters **with** a default.
  `def f(limit: int = 10, store: Store)` is a `SyntaxError`. Write `def f(store: Store, limit: int = 10)`.
* `response_model=BookOut` filters the answer: only the fields declared in `BookOut` are sent.
* `response_model_exclude_none=True` omits optional fields that are `None` (the spec says "omitted, never null").

## Lesson 9 · Dependencies: `Depends`
```python
Store = Annotated[ScriptStore, Depends(get_store)]       # a shortcut name, written once at the top of api.py
Officer = Annotated[User, Depends(require_roles("exams_officer"))]
```
Writing `store: Store` in a function makes FastAPI **build and pass** the store. Writing `user: Officer` makes FastAPI
**check the JWT first** (401/403) and pass the caller. You *use* these; you do not need to understand every detail.

## Lesson 10 · Status codes (the short list)
| Code | Meaning | In ScriptChain |
|---|---|---|
| 200 | OK | reads, accept transfer |
| 201 | Created | create batch, start transfer, submit marks, adjust, approve |
| 401 | I do not know who you are | no/bad/expired token |
| 403 | I know you, but your role may not do this | examiner calls "create batch" |
| 404 | not found | unknown batch / mark / transfer |
| 409 | conflict with the current state | not the custodian, already approved, already accepted |
| 422 | unacceptable request | bad body, bad id format, unknown receiver |
| 503 | a service I need is down | Auth/Script service unreachable (we **fail closed**) |

## Lesson 11 · pytest in 5 minutes
```python
def test_sorted_newest_first():
    result = sorted([{"y": 1}, {"y": 3}], key=lambda b: b["y"], reverse=True)
    assert result[0]["y"] == 3          # `assert` = "this must be true, or the test fails"
```
* `python -m pytest -q` runs everything; `-x` stops at the first failure; `-k name` runs tests whose name contains `name`;
  `-m m1` runs one milestone; `-v` prints one line per test.
* In an `assert a == b` failure pytest prints both sides. **Read them.** The answer is almost always there.
* `with pytest.raises(NotFound): store.get("x")` means "this call must raise NotFound".

## Lesson 12 · Reading a traceback (the red wall of text)
Read **from the bottom**. The last line is the error. The lines above it show *which of your files and lines* led there.
Ignore lines containing `site-packages` (that is the framework). Look for the **first line that points to your code**.
```
E   ResponseValidationError: ... Input should be a valid dictionary    <- the error
    File ".../app/api.py", line 41, in list_batches                     <- YOUR line: look here
```

---
### Self-check before the first task (10 minutes)
1. How do you get the 3 newest items of a list of dicts that have a `"created_at"` text field?
2. What does `Field(min_length=1, max_length=60)` do, and what happens if you misspell `max_length`?
3. Why must `store: Store` come before `limit: int = 10` in a function definition?
4. 404 or 409: a client approves a batch that is already approved?
5. What does `response_model_exclude_none=True` change?

*(Answers: 1 `sorted(..., key=lambda x: x["created_at"], reverse=True)[:3]` · 2 text of 1–60 chars; a misspelling is silently ignored,
so no limit · 3 a parameter without default cannot follow one with a default · 4 409 · 5 fields equal to None are left out of the JSON.)*
