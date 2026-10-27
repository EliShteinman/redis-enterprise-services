import io

import pytest
import requests
from pydantic import SecretStr
from requests.adapters import BaseAdapter
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProtocolError

from redis_enterprise_services.config.edge_settings import EdgeSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.models import ClusterCredentials, ClusterRequest, ClusterResponse
from redis_enterprise_services.exceptions.edge import (
    EdgeError,
    InvalidEdgeRequestError,
    OutcomeUnknownError,
    RequestNotSentError,
    ResponseRejectedError,
)

NETWORK: str = "local"
REQUEST: ClusterRequest = ClusterRequest(
    method="GET",
    url="https://cluster.local:9443/v1/bdbs/1",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


class FakeRelay(BaseAdapter):
    def __init__(self, *, answer: requests.Response | requests.RequestException) -> None:
        super().__init__()
        self._answer: requests.Response | requests.RequestException = answer

    def send(self, request: requests.PreparedRequest, **kwargs: object) -> requests.Response:
        if isinstance(self._answer, requests.RequestException):
            raise self._answer
        self._answer.request = request
        return self._answer

    def close(self) -> None:
        pass


@pytest.fixture
def settings() -> EdgeSettings:
    return Settings().edge


def relay_answer(*, status_code: int, headers: dict[str, str], body: bytes = b"{}") -> requests.Response:
    response: requests.Response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers)
    response.raw = io.BytesIO(initial_bytes=body)
    return response


def send(*, settings: EdgeSettings, answer: requests.Response | requests.RequestException) -> ClusterResponse:
    session: requests.Session = requests.Session()
    session.mount(prefix="http://", adapter=FakeRelay(answer=answer))
    return EdgeClient(settings=settings, session=session).send(network=NETWORK, request=REQUEST)


@pytest.mark.parametrize(argnames="status_code", argvalues=[200, 404])
def test_an_answer_without_edge_error_is_the_cluster_answer(settings: EdgeSettings, status_code: int) -> None:
    answer: requests.Response = relay_answer(status_code=status_code, headers={})

    assert send(settings=settings, answer=answer).status_code == status_code


@pytest.mark.parametrize(
    argnames=("code", "expected"),
    argvalues=[
        ("invalid_request", InvalidEdgeRequestError),
        ("connection_failed", RequestNotSentError),
        ("timeout", OutcomeUnknownError),
        ("response_rejected", ResponseRejectedError),
        ("something_new", OutcomeUnknownError),
    ],
)
def test_an_edge_error_code_is_sorted(settings: EdgeSettings, code: str, expected: type[EdgeError]) -> None:
    answer: requests.Response = relay_answer(status_code=502, headers={settings.headers.error: code})

    with pytest.raises(expected_exception=expected):
        send(settings=settings, answer=answer)


def test_a_rejection_keeps_the_cluster_status(settings: EdgeSettings) -> None:
    headers: dict[str, str] = {
        settings.headers.error: settings.error_codes.response_rejected,
        settings.headers.cluster_status: "201",
    }

    with pytest.raises(expected_exception=ResponseRejectedError) as rejection:
        send(settings=settings, answer=relay_answer(status_code=502, headers=headers))

    assert rejection.value.cluster_status_code == 201


@pytest.mark.parametrize(
    argnames=("error", "expected"),
    argvalues=[
        (
            requests.ConnectionError(
                MaxRetryError(pool=None, url="/", reason=NewConnectionError(None, "refused"))
            ),
            RequestNotSentError,
        ),
        (requests.ConnectionError(ProtocolError("connection aborted")), OutcomeUnknownError),
        (requests.ReadTimeout("read timed out"), OutcomeUnknownError),
    ],
)
def test_a_transport_error_is_sorted(
    settings: EdgeSettings, error: requests.RequestException, expected: type[EdgeError]
) -> None:
    with pytest.raises(expected_exception=expected):
        send(settings=settings, answer=error)
