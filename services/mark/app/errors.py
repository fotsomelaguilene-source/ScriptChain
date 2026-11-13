"""The errors of the business logic (PROVIDED -- do not modify).

Inside the store and the API you never build a JSON error by hand. You simply *raise*
one of these exceptions; ``app.py`` has ONE handler that turns it into the HTTP answer
``{"detail": "<message>"}`` with the right status code.

    raise NotFound("Batch 123 not found")        ->  404
    raise Conflict("Marks are locked")           ->  409   (the request is valid, but the
                                                            current state forbids it)
    raise Unprocessable("Receiver is inactive")  ->  422   (the request itself is not acceptable)
    raise ServiceUnavailable("Auth is down")     ->  503   (a service we depend on is down)

Rule of thumb for 409 vs 422:  409 = "right request, wrong moment";  422 = "wrong request".
"""


class DomainError(Exception):
    """Base class: carries the HTTP status code to answer with."""

    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Unprocessable(DomainError):
    status_code = 422


class ServiceUnavailable(DomainError):
    status_code = 503
