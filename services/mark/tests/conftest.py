"""Shared fixtures, seed constants and the conformance check of every response (PROVIDED).

The application runs IN-PROCESS through TestClient: no network, no port. Each test gets a fresh
application whose store holds the three seed mark batches of data/seed.json, with a deterministic
clock (2026-11-02T09:00:00Z, then one minute more for each new reading) and a sequential id factory.

The Script service is NOT running during these tests: a FAKE custodian client plays its part
(``custodians`` fixture): ``custodians.custody`` says who holds which batch, ``custodians.down = True``
makes it unreachable, ``custodians.calls`` records every question asked.

``api`` wraps TestClient. EVERY response is checked against openapi/mark-openapi-v1.0.yaml: the status
code must be documented for that operation and the body must validate against the documented schema.
"""
from __future__ import annotations

import functools
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import jwt
import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft4Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

from app.clock import NAMESPACE, TickingClock, sequential_ids
from app.main import create_app
from app.ports import BatchNotFound, ScriptServiceUnavailable
from app.security import JWT_ALGORITHM, JWT_SECRET
from app.store import MarkStore

# ----------------------------------------------------------------------------- seed data
OFFICER_ID = "25da51b7-41b2-5975-87ac-2414e676c59d"
EXAMINER_1_ID = "1cae8d57-c5ce-5ba5-b412-663cfcce025e"
EXAMINER_2_ID = "8b927080-46e5-5d85-a537-e615d2187201"
EXAMINER_RETIRED = "90f80b57-1dd3-51ec-8f90-b3f15e28a5c5"
MODERATOR_ID = "ad44afe2-4837-579b-b4e0-eac1231d118e"
HOD_ID = "5662bdb1-2cbb-52f9-8f82-8ddd45457dd7"
STRANGER = "2f0623b4-5bb3-54af-98dd-84c72b942538"
BATCH_NEW = "ab8e1eb0-195b-51a8-95b7-17b938ba6604"
BATCH_CSC201 = "44639172-d92f-574d-9d2c-e2b301fa0195"
BATCH_MTH101 = "7fc9a6e7-dc3c-5086-bef9-ba67911caab3"
BATCH_NET301 = "65424a60-800e-5b94-9846-0040f14e804c"
UNKNOWN_BATCH = "5fcf0a6e-c7a8-5f0f-b7c6-b60232d6d07c"
UNKNOWN_TRANSFER = "8e0e0140-a698-5c0c-98a5-a30afcb99184"
UNKNOWN_MARK = "c9d6ac0e-63f0-5400-82b4-2f94a945a0f6"
UNKNOWN_USER = "559c6896-2315-5582-a1ad-6d995dd536b2"
TRANSFER_ACCEPTED = "aabadfdc-ed7b-557d-8740-86f3045ce1b6"
TRANSFER_PENDING = "fd5ed9d1-336b-5ecc-9422-2ece2d4e0ad9"
MARK_CN1001 = "e7896ce7-cead-5c28-9157-6b17bcaa47df"
MARK_CN1002 = "32bb386b-34b1-5e68-82a0-ed1b8c06d6af"
MARK_CN1003 = "4bc7b600-e9a1-5ee6-a45a-94e19118793d"
MARK_CN2001 = "becce37c-dca8-5100-92fa-dd2c02425fdb"
MARK_CN2002 = "7b94990c-9c3d-591c-98ba-3ad476afec62"
MARK_CN3001 = "a1f161bb-d427-545b-9633-6e65c920bd83"
MARK_CN3002 = "57ecb667-3c7e-58b2-875e-6486a5aa6073"

MARK_KEYS = {"id", "batch_id", "candidate_number", "original_score", "current_score", "entered_by",
             "custodian_id_at_entry", "entered_at"}
ADJUSTMENT_KEYS = {"id", "mark_id", "old_score", "new_score", "reason", "adjusted_by", "adjusted_at"}

FROZEN_CREATED = "2026-11-02T09:00:00Z"            # the test clock's first reading
NEW_IDS = [str(uuid.uuid5(NAMESPACE, f"new-{n}")) for n in range(1, 40)]   # ids the test factory hands out
FIRST_NEW_ID = NEW_IDS[0]


@dataclass(frozen=True)
class Actor:
    """Somebody who calls the API: a user id and a role."""

    id: str
    role: str


OFFICER = Actor(OFFICER_ID, "exams_officer")
EXAMINER_ONE = Actor(EXAMINER_1_ID, "examiner")
EXAMINER_TWO = Actor(EXAMINER_2_ID, "examiner")
MODERATOR = Actor(MODERATOR_ID, "moderator")
HOD = Actor(HOD_ID, "hod")


def bulk(*pairs: tuple[str, object]) -> dict:
    """A bulk-submission payload from (candidate_number, score) pairs: bulk(("CN0001", 50), ("CN0002", 61.5))."""
    return {"entries": [{"candidate_number": number, "score": score} for number, score in pairs]}


def key(name: str = "key-0001") -> dict:
    """The Idempotency-Key header (at least 8 characters)."""
    return {"Idempotency-Key": name}


def make_token(actor: Actor, *, expires_in: int = 3600, secret: str = JWT_SECRET, **claims) -> str:
    """A signed JWT for *actor*. Use expires_in=-60 for an expired one, secret="x" for a forged one."""
    payload = {"sub": actor.id, "role": actor.role, "exp": int(time.time()) + expires_in}
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


# ----------------------------------------------------------------------------- the specification
ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "openapi" / "mark-openapi-v1.0.yaml"
SPEC = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
SPEC_URI = "urn:scriptchain:mark-openapi-v1.0"
REGISTRY = Registry().with_resource(SPEC_URI, Resource.from_contents(SPEC, default_specification=DRAFT4))
HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")

FORMATS = FormatChecker(formats=())
UUID_TEXT = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")


@FORMATS.checks("uuid", raises=ValueError)
def _is_uuid(value: object) -> bool:
    return not isinstance(value, str) or bool(UUID_TEXT.fullmatch(value))


@FORMATS.checks("date-time", raises=ValueError)
def _is_utc_timestamp(value: object) -> bool:
    """RFC 3339, and (project rule) in UTC with the "Z" designator."""
    if not isinstance(value, str):
        return True
    return bool(UTC_TIMESTAMP.fullmatch(value)) and datetime.fromisoformat(value) is not None


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _resolve(pointer: str) -> object:
    node: object = SPEC
    for token in pointer.lstrip("/").split("/"):
        node = node[token.replace("~1", "/").replace("~0", "~")]
    return node


@functools.cache
def validator(pointer: str) -> Draft4Validator:
    """A validator for the schema found at *pointer* (a JSON pointer into the spec)."""
    return Draft4Validator({"$ref": f"{SPEC_URI}#{pointer}"}, registry=REGISTRY, format_checker=FORMATS)


def schema_errors(pointer: str, instance: object) -> list[str]:
    errors = sorted(validator(pointer).iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(body)'}: {e.message}" for e in errors]


def documented_response(method: str, template: str, code: str) -> tuple[dict, str]:
    """The response object the spec documents for this operation and code, and its pointer."""
    operation = SPEC["paths"][template][method]
    if code not in operation["responses"]:
        raise AssertionError(
            f"{method.upper()} {template} answered {code}, a status code the specification "
            f"does not document for this operation (documented: {', '.join(operation['responses'])})")
    pointer = f"/paths/{_escape(template)}/{method}/responses/{code}"
    response = operation["responses"][code]
    while "$ref" in response:
        pointer = response["$ref"].removeprefix("#")
        response = _resolve(pointer)
    return response, pointer


def check_against_spec(response, method: str, template: str) -> None:
    """Fail unless *response* is one the specification allows for this operation."""
    method = method.lower()
    documented, pointer = documented_response(method, template, str(response.status_code))
    where = f"{method.upper()} {template} -> {response.status_code}"
    if "content" not in documented:
        assert response.content == b"", f"{where}: the body must be empty, got {response.content[:80]!r}"
        return
    assert response.headers.get("content-type", "").startswith("application/json"), \
        f"{where}: Content-Type is {response.headers.get('content-type')!r}, not JSON"
    problems = schema_errors(f"{pointer}/content/application~1json/schema", response.json())
    assert not problems, f"{where}: the body does not match the specification: " + "; ".join(problems[:6])


def spec_operations() -> set[tuple[str, str]]:
    """Every (METHOD, path template) the specification documents."""
    return {(method.upper(), path) for path, item in SPEC["paths"].items()
            for method in item if method in HTTP_METHODS}


def success_codes(method: str, template: str) -> set[str]:
    return {code for code in SPEC["paths"][template][method.lower()]["responses"] if code.startswith("2")}


def success_schema(method: str, template: str) -> dict | None:
    """The schema of the success response of one operation ($refs followed), None for 204."""
    documented, _ = documented_response(method.lower(), template, min(success_codes(method, template)))
    if "content" not in documented:
        return None
    schema = documented["content"]["application/json"]["schema"]
    while "$ref" in schema:
        schema = _resolve(schema["$ref"].removeprefix("#"))
    return schema


def operations_served(app) -> dict[tuple[str, str], dict]:
    """(METHOD, path) -> operation, for every operation the application documents in app.openapi()."""
    return {(method.upper(), path): operation
            for path, item in app.openapi()["paths"].items()
            for method, operation in item.items() if method in HTTP_METHODS}


def declared_schema(app, operation: dict, code: str) -> dict | None:
    """The schema the application declares for one response of *operation* ($ref followed)."""
    response = operation["responses"][code]
    if "content" not in response:
        return None
    schema = response["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = app.openapi()["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


class SpecClient:
    """TestClient whose every response is checked against the specification."""

    def __init__(self, app, **kwargs) -> None:
        self.http = TestClient(app, **kwargs)

    def call(self, method: str, template: str, *, as_: Actor | None = None, token: str | None = None,
             params=None, json=None, headers=None, **path_values):
        """Call an operation. as_=OFFICER sends a valid token of that actor; token="..." sends exactly that
        string; neither sends no Authorization header at all."""
        url = template.format(**path_values) if path_values else template
        headers = dict(headers or {})
        if as_ is not None:
            headers["Authorization"] = f"Bearer {make_token(as_)}"
        elif token is not None:
            headers["Authorization"] = f"Bearer {token}"
        todo = None
        try:
            response = self.http.request(method, url, params=params, json=json, headers=headers)
        except NotImplementedError as exc:          # a TODO of the starter: name it, without
            todo = str(exc)                         # forty lines of framework traceback
        if todo is not None:
            pytest.fail(f"{method} {url} reached {todo}", pytrace=False)
        if response.status_code in (404, 405) and response.json().get("detail") in ("Not Found", "Method Not Allowed"):
            pytest.fail(f"{method} {url}: the application has NO such route -- did you write the "
                        f"@router.{method.lower()}(...) decorator of this path operation?", pytrace=False)
        check_against_spec(response, method, template)
        return response

    def get(self, template: str, **kwargs):
        return self.call("GET", template, **kwargs)

    def post(self, template: str, **kwargs):
        return self.call("POST", template, **kwargs)


# ----------------------------------------------------------------------------- fakes and fixtures
class FakeCustodians:
    """Plays the Script service: no network. ``custody`` maps batch id -> custodian user id."""

    def __init__(self, custody: dict[str, str]) -> None:
        self.custody = dict(custody)
        self.down = False
        self.calls: list[tuple[str, str]] = []          # (batch_id, token) of every question asked

    def get_custodian(self, batch_id: str, token: str) -> str:
        self.calls.append((batch_id, token))
        if self.down:
            raise ScriptServiceUnavailable("the script service is down")
        if batch_id not in self.custody:
            raise BatchNotFound(batch_id)
        return self.custody[batch_id]


def make_store(**kwargs) -> MarkStore:
    """A store with the seed mark batches, the test clock and the sequential ids."""
    kwargs.setdefault("clock", TickingClock())
    kwargs.setdefault("new_id", sequential_ids())
    return MarkStore.from_seed(**kwargs)


@pytest.fixture
def store() -> MarkStore:
    return make_store()


@pytest.fixture
def custodians() -> FakeCustodians:
    """In the Script service: examiner 1 holds the new batch and NET301, examiner 2 holds MTH101."""
    return FakeCustodians({BATCH_NEW: EXAMINER_1_ID, BATCH_NET301: EXAMINER_1_ID,
                           BATCH_CSC201: EXAMINER_1_ID, BATCH_MTH101: EXAMINER_2_ID})


@pytest.fixture
def app(store, custodians):
    return create_app(store, custodians)


@pytest.fixture
def api(app) -> SpecClient:
    return SpecClient(app)
