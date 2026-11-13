"""python -m app  -> serve the Mark service on port 8002 (PROVIDED).

Needs the Script service on SCRIPT_SERVICE_URL (default http://localhost:8001) for the custodian check.
"""
import os

import uvicorn

from app.main import create_app

if __name__ == "__main__":
    uvicorn.run(create_app(), host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8002")))
