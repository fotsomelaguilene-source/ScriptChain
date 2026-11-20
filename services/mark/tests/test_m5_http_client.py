"""M5 -- HttpCustodianClient: how the Mark service talks to the Script service (task K5, written by KELLY).

No real network: httpx.MockTransport(handler) lets the test decide what "the Script service" answers.
``handler(request)`` receives the request the client sent and returns an httpx.Response -- or RAISES an
httpx error to simulate a timeout. Every test counts how many times the handler was called: that is how we
prove the retry rules (1 + retries attempts at most, none for a 404).
"""
import httpx
import pytest

from app.ports import BatchNotFound, HttpCustodianClient, ScriptServiceUnavailable
from tests.conftest import BATCH_NEW, EXAMINER_1_ID

pytestmark = pytest.mark.m5


class FakeNetwork:
    """A pretend Script service. ``script`` is a list of things to do, one per call: an httpx.Response to return
    or an Exception to raise; the last item repeats forever."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = self.script[min(len(self.requests), len(self.script)) - 1]
        if isinstance(step, Exception):
            raise step
        return step

    def client(self, **kwargs) -> HttpCustodianClient:
        return HttpCustodianClient("http://script.test", transport=httpx.MockTransport(self), **kwargs)


OK = httpx.Response(200, json={"batch_id": BATCH_NEW, "custodian_id": EXAMINER_1_ID})


def test_a_200_answer_gives_the_custodian_id_and_forwards_the_token():
    """WORKED EXAMPLE (given): read it line by line before writing the others."""
    network = FakeNetwork(OK)
    custodian = network.client().get_custodian(BATCH_NEW, "my-token")
    assert custodian == EXAMINER_1_ID
    assert len(network.requests) == 1
    assert network.requests[0].url.path == f"/v1/batches/{BATCH_NEW}/custodian"
    assert network.requests[0].headers["Authorization"] == "Bearer my-token"


def test_a_404_means_the_batch_is_unknown_and_is_not_retried():
    network = FakeNetwork(httpx.Response(404, json={"detail": "not found"}))
    with pytest.raises(BatchNotFound):
        network.client().get_custodian(BATCH_NEW, "t")
    assert len(network.requests) == 1                    # one attempt only: asking again would not help


def test_a_timeout_is_retried_then_fails_closed():
    network = FakeNetwork(httpx.ReadTimeout("too slow"))                 # the same failure forever
    with pytest.raises(ScriptServiceUnavailable):
        network.client(retries=2).get_custodian(BATCH_NEW, "t")
    assert len(network.requests) == 3                    # 1 first attempt + 2 retries


def test_a_connection_error_is_retried_then_fails_closed():
    network = FakeNetwork(httpx.ConnectError("refused"))
    with pytest.raises(ScriptServiceUnavailable):
        network.client(retries=1).get_custodian(BATCH_NEW, "t")
    assert len(network.requests) == 2                    # 1 first attempt + 1 retry


def test_a_server_error_then_a_good_answer_succeeds_on_the_retry():
    network = FakeNetwork(httpx.Response(503), OK)       # first call 503, second call 200
    assert network.client(retries=2).get_custodian(BATCH_NEW, "t") == EXAMINER_1_ID
    assert len(network.requests) == 2                    # it stopped as soon as it had a good answer


def test_a_server_that_keeps_failing_fails_closed_after_all_the_attempts():
    network = FakeNetwork(httpx.Response(500))           # 500 forever
    with pytest.raises(ScriptServiceUnavailable):
        network.client(retries=2).get_custodian(BATCH_NEW, "t")
    assert len(network.requests) == 3


@pytest.mark.parametrize("code", [401, 403])
def test_a_refusal_is_not_retried_and_is_treated_as_unavailable(code):
    network = FakeNetwork(httpx.Response(code))
    with pytest.raises(ScriptServiceUnavailable):        # not BatchNotFound: the batch may well exist
        network.client(retries=2).get_custodian(BATCH_NEW, "t")
    assert len(network.requests) == 1                    # retrying a refusal is pointless
