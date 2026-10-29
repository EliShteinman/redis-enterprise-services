import io
from unittest.mock import create_autospec

import pytest
import requests
from pydantic import SecretStr
from urllib3.connection import HTTPConnection
from urllib3.connectionpool import ConnectionPool
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError, ProtocolError, SSLError

from redis_enterprise_services.config.edge_settings import EdgeSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.connection.models import ClusterCredentials
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.exceptions.edge import (
    EdgeError,
    InvalidEdgeRequestError,
    OutcomeUnknownError,
    RequestNotSentError,
    ResponseRejectedError,
)

NETWORK: str = "local"
POOL: ConnectionPool = create_autospec(spec=ConnectionPool, instance=True)
CONNECTION: HTTPConnection = create_autospec(spec=HTTPConnection, instance=True)
REQUEST: ClusterRequest = ClusterRequest(
    method="GET",
    url="https://cluster.local:9443/v1/bdbs/1",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


@pytest.fixture
def settings() -> EdgeSettings:
    return load_settings().edge


def relay_answer(*, status_code: int, headers: dict[str, str], body: bytes = b"{}") -> requests.Response:
    response: requests.Response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers)
    response.raw = io.BytesIO(initial_bytes=body)
    return response


def send(
    *,
    settings: EdgeSettings,
    answer: requests.Response | requests.RequestException,
    monkeypatch: pytest.MonkeyPatch,
) -> ClusterResponse:
    def fake_post(**kwargs: object) -> requests.Response:
        if isinstance(answer, requests.RequestException):
            raise answer
        return answer

    monkeypatch.setattr(target=requests, name="post", value=fake_post)
    return EdgeClient(settings=settings).send(network=NETWORK, request=REQUEST)


@pytest.mark.parametrize(argnames="status_code", argvalues=[200, 404])
def test_an_answer_without_edge_error_is_the_cluster_answer(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings, status_code: int
) -> None:
    answer: requests.Response = relay_answer(status_code=status_code, headers={})

    assert send(settings=settings, answer=answer, monkeypatch=monkeypatch).status_code == status_code


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
def test_an_edge_error_code_is_sorted(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings, code: str, expected: type[EdgeError]
) -> None:
    answer: requests.Response = relay_answer(status_code=502, headers={settings.headers.error: code})

    with pytest.raises(expected_exception=expected):
        send(settings=settings, answer=answer, monkeypatch=monkeypatch)


def test_a_rejection_keeps_the_cluster_status(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings
) -> None:
    headers: dict[str, str] = {
        settings.headers.error: settings.error_codes.response_rejected,
        settings.headers.cluster_status: "201",
    }

    with pytest.raises(expected_exception=ResponseRejectedError) as rejection:
        send(
            settings=settings, answer=relay_answer(status_code=502, headers=headers), monkeypatch=monkeypatch
        )

    assert rejection.value.cluster_status_code == 201


@pytest.mark.parametrize(
    argnames=("error", "expected"),
    argvalues=[
        (
            requests.ConnectionError(
                MaxRetryError(pool=POOL, url="/", reason=NewConnectionError(CONNECTION, "refused"))
            ),
            RequestNotSentError,
        ),
        (
            requests.ConnectTimeout(
                MaxRetryError(pool=POOL, url="/", reason=ConnectTimeoutError("timed out"))
            ),
            RequestNotSentError,
        ),
        (
            requests.exceptions.SSLError(
                MaxRetryError(pool=POOL, url="/", reason=SSLError("eof after sending"))
            ),
            OutcomeUnknownError,
        ),
        (requests.ConnectionError(ProtocolError("connection aborted")), OutcomeUnknownError),
        (requests.ReadTimeout("read timed out"), OutcomeUnknownError),
    ],
)
def test_a_transport_error_is_sorted(
    monkeypatch: pytest.MonkeyPatch,
    settings: EdgeSettings,
    error: requests.RequestException,
    expected: type[EdgeError],
) -> None:
    with pytest.raises(expected_exception=expected):
        send(settings=settings, answer=error, monkeypatch=monkeypatch)
