"""The Mark service's one outside dependency: the Script service (the custodian check).

Before it saves marks, the Mark service asks the Script service ONE question:
"who is the current custodian of this batch?"  (GET /v1/batches/{batch_id}/custodian).
We hide that HTTP call behind a small *port*:

    client.get_custodian(batch_id, token)  ->  the custodian's user id (a string)
        raises BatchNotFound              when the Script service does not know the batch (it answered 404)
        raises ScriptServiceUnavailable   when we could not get a trustworthy answer (down, too slow, 5xx)

* In the TESTS of the API, a fake client is plugged in (no network).
* ``HttpCustodianClient`` is the real one (task K5, written by Kelly: timeouts and retries are networking!).
  It is tested with httpx.MockTransport -- a pretend network -- in tests/test_m5_http_client.py.

Design rule from the architecture brief: Mark FAILS CLOSED. If we cannot verify the custodian we do
NOT accept the marks (the API answers 503); we never accept unverified marks.
"""
from typing import Protocol

import httpx


class BatchNotFound(Exception):
    """The Script service does not know this batch (it answered 404)."""


class ScriptServiceUnavailable(Exception):
    """No trustworthy answer from the Script service: timeout, connection error, 5xx, or a refusal."""


class CustodianClient(Protocol):
    def get_custodian(self, batch_id: str, token: str) -> str:
        """The id of the current custodian of *batch_id*. *token* is the caller's JWT, forwarded."""


class HttpCustodianClient:
    """The real client: calls the Script service over HTTP.

    base_url   e.g. "http://localhost:8001"
    timeout    seconds to wait for ONE attempt (one value for all service-to-service calls; documented)
    retries    how many EXTRA attempts after the first one (a custodian check is a safe read, so retrying is fine)
    transport  only for tests: pass httpx.MockTransport(handler) to fake the network
    """

    def __init__(self, base_url: str, *, timeout: float = 2.0, retries: int = 2,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.retries = retries
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def get_custodian(self, batch_id: str, token: str) -> str:
        """Ask the Script service. Rules (the tests check each one):

        * send the header  Authorization: Bearer <token>
        * 200            -> return the "custodian_id" of the JSON body
        * 404            -> raise BatchNotFound(batch_id)           (no retry)
        * other 4xx      -> raise ScriptServiceUnavailable           (no retry: asking again will not help)
        * 5xx, or a timeout / connection problem (httpx.TransportError) -> try again;
          after 1 + self.retries attempts in total, raise ScriptServiceUnavailable
        """
        # TODO M5 (task K5): loop `for attempt in range(self.retries + 1):`
        #   inside: try: response = self._client.get(f"/v1/batches/{batch_id}/custodian", headers={...})
        #           except httpx.TransportError: remember the failure and `continue`
        #   then look at response.status_code as the docstring says (200 / 404 / >= 500 -> continue / other -> raise).
        #   after the loop: raise ScriptServiceUnavailable(...)
        raise NotImplementedError("TODO M5: HttpCustodianClient.get_custodian -- call the Script service with retries")
