"""Where time and identity come from (PROVIDED -- do not modify).

The store never calls ``datetime.now`` or ``uuid.uuid4`` by itself. It receives a *clock*
and an *id factory* when it is built:

* in production: the real UTC time and random UUIDs;
* in the tests: a deterministic clock and deterministic ids, so that the tests know in
  advance which ``id`` and which timestamp a new record must have.

Why? A test cannot check "created == now" if "now" changes every microsecond.
"""
import itertools
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

NAMESPACE = uuid.UUID("5c71a2b0-4e6d-5d0a-9a53-2b7e0f3c9a11")
FROZEN_START = datetime(2026, 11, 2, 9, 0, 0, tzinfo=timezone.utc)
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"      # e.g. 2026-11-02T09:00:00Z


def utc_now() -> datetime:
    """The real clock: current time, timezone-aware, UTC."""
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    """The real id factory: a random UUID."""
    return uuid.uuid4()


def stamp(moment: datetime) -> str:
    """Format a datetime the way the API shows it: UTC, seconds, trailing Z."""
    return moment.astimezone(timezone.utc).strftime(TIMESTAMP_FORMAT)


class TickingClock:
    """Deterministic clock: first call returns *start*, every later call one *step* more."""

    def __init__(self, start: datetime = FROZEN_START, step: timedelta = timedelta(minutes=1)) -> None:
        if start.tzinfo is None:
            raise ValueError("the start of a clock must be timezone-aware (UTC)")
        self._next = start
        self.step = step

    def __call__(self) -> datetime:
        now = self._next
        self._next = now + self.step
        return now


def sequential_ids(prefix: str = "new") -> Callable[[], uuid.UUID]:
    """Deterministic id factory: uuid5("<prefix>-1"), uuid5("<prefix>-2"), ..."""
    counter = itertools.count(1)

    def next_id() -> uuid.UUID:
        return uuid.uuid5(NAMESPACE, f"{prefix}-{next(counter)}")

    return next_id
