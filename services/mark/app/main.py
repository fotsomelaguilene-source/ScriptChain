"""The application factory create_app(store, custodians) (PROVIDED -- do not modify)."""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import api
from app.errors import DomainError
from app.ports import CustodianClient, HttpCustodianClient
from app.store import MarkStore

DESCRIPTION = ("ScriptChain Mark Service v1.0: marks, moderation adjustments and approval "
               "(synthetic data; in-memory implementation).")


def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """NotFound -> 404, Conflict -> 409, Unprocessable -> 422, ServiceUnavailable -> 503."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def create_app(store: MarkStore | None = None, custodians: CustodianClient | None = None) -> FastAPI:
    app = FastAPI(title="ScriptChain Mark Service", version="1.0.0", description=DESCRIPTION)
    app.include_router(api.router)
    app.state.store = store if store is not None else MarkStore.from_seed()
    app.state.custodians = custodians if custodians is not None else HttpCustodianClient(
        os.environ.get("SCRIPT_SERVICE_URL", "http://localhost:8001"))
    app.add_exception_handler(DomainError, domain_error_handler)

    @app.get("/health/live", include_in_schema=False)
    def live() -> dict:
        return {"status": "alive"}

    @app.get("/health/ready", include_in_schema=False)
    def ready() -> dict:
        return {"status": "ready"}

    return app
