# 03 · Reading an OpenAPI file, and turning it into code

The YAML files in `services/*/openapi/` are **the contract**. The tests read the same files. If your code and the YAML
disagree, **your code is wrong** (unless the lecturer changes the contract).

## The skeleton of an OpenAPI file

```yaml
paths:                          # every URL
  /v1/batches/{batch_id}:       #   one path
    get:                        #     one OPERATION = method + path
      operationId: getBatch     #       its name (we use it in docstrings)
      parameters: ...           #       path / query / header values
      requestBody: ...          #       the JSON the client sends
      responses:                #       every answer the API may give
        '200': ...              #         success: which schema?
        '404': ...              #         errors: documented too
components:
  schemas: ...                  # the shapes (BatchSchema, ...)   -> your pydantic models
  responses: ...                # reusable error answers          -> raised by errors.py
  parameters: ...               # reusable parameters (limit, offset, batch_id)
```
`$ref: '#/components/schemas/BatchSchema'` simply means "see that schema over there".

## Dictionary: YAML word → Python code

| In the YAML | In pydantic / FastAPI |
|---|---|
| `type: string` | `str` |
| `type: integer` | `int` |
| `type: number` | `float` |
| `type: boolean` | `bool` |
| `type: array` + `items:` | `list[ItemType]` |
| `format: uuid` | `UUID` |
| `format: date-time` | `datetime` |
| `minLength: 1` / `maxLength: 60` | `Field(min_length=1, max_length=60)` |
| `pattern: '^CN[0-9]{4}$'` | `Field(pattern=r"^CN[0-9]{4}$")` |
| `minimum: 1` / `maximum: 100` | `Field(ge=1, le=100)` |
| `minItems: 1` / `maxItems: 50` (on an array) | `Field(min_length=1, max_length=50)` |
| `uniqueItems: true` | a `@field_validator` that refuses duplicates |
| `enum: [a, b]` | a `StrEnum` class |
| listed under `required:` | the field has **no default** |
| **not** listed under `required:` | `type \| None = None` (and `response_model_exclude_none=True`) |
| `in: query`, `default: 10` | `limit: Annotated[int, Query(ge=1, le=100)] = 10` |
| `in: path` | a parameter with the same name as in `{...}` |
| `in: header` | `Annotated[str, Header(...)]` |
| `'201':` under `responses` | `status_code=status.HTTP_201_CREATED` in the decorator |
| `$ref` to a schema in the 200/201 answer | `response_model=ThatSchema` in the decorator |

## Worked mini-example (library, not ScriptChain)

```yaml
BookSchema:
  type: object
  required: [id, title]
  properties:
    id:      {type: string, format: uuid}
    title:   {type: string, maxLength: 80}
    subtitle:{type: string}
```
becomes
```python
class BookSchema(BaseModel):
    id: UUID
    title: str
    subtitle: str | None = None      # not in `required` -> optional
```
(`maxLength` is a rule for what clients **send**; a response model does not need to repeat it.)

## Request model or response model?

* **Request** schemas (`CreateBatchSchema`, `BulkMarksSchema`, …): they **validate** → put every rule of the YAML in them.
* **Response** schemas (`BatchSchema`, `MarkSchema`, …): they **filter and describe** → right fields, right types,
  in the order of the YAML. Their job is also to *hide* what the stored record contains and the spec does not show
  (`scripts`, `transfers`, `adjustments`).

## Worksheet for K0 (Kelly answers in the report, 15 minutes)

Open `services/script/openapi/script-openapi-v1.0.yaml` and answer:
1. How many operations does it contain? Which one is the only operation whose path does **not** start with `/v1/batches`?
2. Which status codes can `startTransfer` answer? What does each mean *for this operation*?
3. What is the difference between `401` and `403` here? Which operations can never answer `403`, and why?
4. Which fields of `TransferSchema` are `required`? Which one is optional and when is it absent?
5. In `CreateBatchSchema`, which rule does `uniqueItems` express, and where do you enforce it in Python?
6. Open `mark-openapi-v1.0.yaml`: which operation has a **header** parameter, and why does it exist?
7. In the **Mark** spec, which operations need the `hod` role or the `moderator` role?
8. Start the Script service (`make run-script`), open http://127.0.0.1:8001/docs and compare: does the page show the same
   operations as the YAML? (It is generated from your code — when you finish, the two must match: that is the *contract test*.)

## Tools
* **Swagger UI**: http://127.0.0.1:8001/docs (Script) and http://127.0.0.1:8002/docs (Mark) — click **Authorize**, paste a token
  from `python tools/make_token.py officer`, then **Try it out**.
* The raw generated contract of your code: http://127.0.0.1:8001/openapi.json
* The Swagger Editor (https://editor.swagger.io) can display the YAML files nicely: paste the file in.
