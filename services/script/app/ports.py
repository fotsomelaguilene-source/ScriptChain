"""The Script service's one outside dependency: the user directory (PROVIDED).

When an officer hands scripts to someone, we must check that this someone exists, is active
and is an examiner. In the finished system that question goes to the Auth service over HTTP
(``GET /v1/users/{id}``). In this lab the Auth service does not exist yet, so we hide it
behind a small *port* -- an interface with ONE method:

    directory.get_user("<uuid>")  ->  {"id", "username", "role", "is_active"}  or  None

* ``StaticUserDirectory`` answers from data/users.json (used by ``python -m app``).
* The tests plug in their own fakes, including one that is "down" (raises DirectoryUnavailable).

Later (roadmap, docs/08) you will add ``HttpUserDirectory`` without touching a single line of
the API or the store: that is the benefit of a port.
"""
import copy
import json
from pathlib import Path
from typing import Protocol

USERS_PATH = Path(__file__).resolve().parent.parent / "data" / "users.json"


class DirectoryUnavailable(Exception):
    """The Auth service cannot be reached (the API must answer 503: fail closed)."""


class UserDirectory(Protocol):
    def get_user(self, user_id: str) -> dict | None:
        """The user with this id, or None when nobody has it. May raise DirectoryUnavailable."""


class StaticUserDirectory:
    """A directory read from a JSON file."""

    def __init__(self, users: list[dict]) -> None:
        self._users = {user["id"]: user for user in users}

    @classmethod
    def from_file(cls, path: Path = USERS_PATH) -> "StaticUserDirectory":
        with path.open(encoding="utf-8") as fh:
            return cls(json.load(fh))

    def get_user(self, user_id: str) -> dict | None:
        user = self._users.get(str(user_id))
        return copy.deepcopy(user) if user else None
