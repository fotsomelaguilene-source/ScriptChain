"""Print a JWT for a seed user, to try the API by hand (Swagger /docs -> Authorize, or curl).

    python tools/make_token.py --list                 the seed users and their ids
    python tools/make_token.py officer                a token for the first user with that role
    python tools/make_token.py examiner 2             the 2nd examiner of the list
    python tools/make_token.py expired                an EXPIRED token (to see a 401)

The secret is the same as the services use: JWT_SECRET (default: the dev secret of app/security.py).
"""
import json
import os
import sys
import time
from pathlib import Path

import jwt

SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-please-0123456789")
USERS = json.loads((Path(__file__).resolve().parent.parent / "services/script/data/users.json").read_text())
ALIASES = {"officer": "exams_officer"}


def token_for(role: str, nth: int = 1, expires_in: int = 3600) -> str:
    role = ALIASES.get(role, role)
    candidates = [u for u in USERS if u["role"] == role and u["is_active"]]
    user = candidates[nth - 1]
    return jwt.encode({"sub": user["id"], "role": user["role"], "exp": int(time.time()) + expires_in}, SECRET, algorithm="HS256")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--list":
        for user in USERS:
            print(f'{user["role"]:14} {user["id"]}  {user["username"]}{"" if user["is_active"] else "  (inactive)"}')
        sys.exit(0)
    if args[0] == "expired":
        print(token_for("examiner", expires_in=-60)); sys.exit(0)
    print(token_for(args[0], int(args[1]) if len(args) > 1 else 1))
