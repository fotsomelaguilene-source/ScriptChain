"""The application factory create_app(store, directory) (PROVIDED -- do not modify).

It includes the router of api.py, registers ONE handler that turns every error of
app/errors.py into ``{"detail": "<message>"}`` with the right status code, and adds two
health probes used later by Docker and Kubernetes (liveness / readiness).
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import api
from app.errors import DomainError
from app.ports import StaticUserDirectory, UserDirectory
from app.store import ScriptStore

DESCRIPTION = ("ScriptChain Script Service v1.0: batches of exam scripts and their custody transfers "
               "(synthetic data; in-memory implementation).")


def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """NotFound -> 404, Conflict -> 409, Unprocessable -> 422, ServiceUnavailable -> 503."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def create_app(store: ScriptStore | None = None, directory: UserDirectory | None = None) -> FastAPI:
    app = FastAPI(title="ScriptChain Script Service", version="1.0.0", description=DESCRIPTION)
    app.include_router(api.router)
    app.state.store = store if store is not None else ScriptStore.from_seed()
    app.state.directory = directory if directory is not None else StaticUserDirectory.from_file()
    app.add_exception_handler(DomainError, domain_error_handler)

    @app.get("/health/live", include_in_schema=False)
    def live() -> dict:
        return {"status": "alive"}

    @app.get("/health/ready", include_in_schema=False)
    def ready() -> dict:
        return {"status": "ready"}

    return app
