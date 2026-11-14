import io
from unittest.mock import create_autospec

import pytest
import requests
from pydantic import SecretStr
from urllib3.connection import HTTPConnection
from urllib3.connectionpool import ConnectionPool
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError, ProtocolError, SSLError

from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.edge_settings import EdgeSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.header_builder import EdgeHeaderBuilder
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.edge.response_reader import EdgeResponseReader
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.edge import (
    EdgeConnectionFailedError,
    EdgeError,
    EdgeOutcomeUnknownError,
    EdgeRejectedRequestError,
    EdgeRejectedResponseError,
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


def relay_response(*, status_code: int, headers: dict[str, str], body: bytes = b"{}") -> requests.Response:
    response: requests.Response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers)
    response.raw = io.BytesIO(initial_bytes=body)
    return response


def send_through_relay_answering(
    *,
    settings: EdgeSettings,
    relay_outcome: requests.Response | requests.RequestException,
    monkeypatch: pytest.MonkeyPatch,
) -> ClusterResponse:
    def fake_post(**kwargs: object) -> requests.Response:
        if isinstance(relay_outcome, requests.RequestException):
            raise relay_outcome
        return relay_outcome

    monkeypatch.setattr(target=requests, name="post", value=fake_post)
    return EdgeClient(
        settings=settings,
        header_builder=EdgeHeaderBuilder(settings=settings),
        response_reader=EdgeResponseReader(settings=settings),
    ).send(network=NETWORK, request=REQUEST)


@pytest.mark.parametrize(argnames="status_code", argvalues=[200, 404])
def test_a_relay_response_without_edge_error_unwraps_to_the_cluster_response(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings, status_code: int
) -> None:
    relay_response_value: requests.Response = relay_response(status_code=status_code, headers={})

    assert (
        send_through_relay_answering(
            settings=settings, relay_outcome=relay_response_value, monkeypatch=monkeypatch
        ).status_code
        == status_code
    )


@pytest.mark.parametrize(
    argnames=("code", "expected"),
    argvalues=[
        ("invalid_request", EdgeRejectedRequestError),
        ("connection_failed", EdgeConnectionFailedError),
        ("timeout", EdgeOutcomeUnknownError),
        ("response_rejected", EdgeRejectedResponseError),
        ("internal_error", EdgeOutcomeUnknownError),
    ],
)
def test_an_edge_error_code_maps_to_its_edge_error(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings, code: str, expected: type[EdgeError]
) -> None:
    relay_response_value: requests.Response = relay_response(
        status_code=502, headers={settings.headers.edge_error_code: code}
    )

    with pytest.raises(expected_exception=expected):
        send_through_relay_answering(
            settings=settings, relay_outcome=relay_response_value, monkeypatch=monkeypatch
        )


def test_a_body_that_is_not_json_without_an_edge_error_code_is_an_unknown_outcome(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings
) -> None:
    gateway_page: requests.Response = relay_response(
        status_code=504, headers={}, body=b"<html>timeout</html>"
    )

    with pytest.raises(expected_exception=EdgeOutcomeUnknownError):
        send_through_relay_answering(settings=settings, relay_outcome=gateway_page, monkeypatch=monkeypatch)


def test_a_cluster_state_id_that_is_not_a_number_is_ignored(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings
) -> None:
    headers: dict[str, str] = {settings.headers.cluster_state_id: "abc"}
    relay_response_value: requests.Response = relay_response(status_code=200, headers=headers)

    assert (
        send_through_relay_answering(
            settings=settings, relay_outcome=relay_response_value, monkeypatch=monkeypatch
        ).cluster_state_id
        is None
    )


def test_a_relay_rejected_response_keeps_the_cluster_status(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings
) -> None:
    headers: dict[str, str] = {
        settings.headers.edge_error_code: settings.error_codes.response_rejected,
        settings.headers.cluster_status_code: "201",
    }

    with pytest.raises(expected_exception=EdgeRejectedResponseError) as rejected_response:
        send_through_relay_answering(
            settings=settings,
            relay_outcome=relay_response(status_code=502, headers=headers),
            monkeypatch=monkeypatch,
        )

    assert rejected_response.value.cluster_status_code == 201


@pytest.mark.parametrize(
    argnames=("error", "expected"),
    argvalues=[
        (
            requests.ConnectionError(
                MaxRetryError(pool=POOL, url="/", reason=NewConnectionError(CONNECTION, "refused"))
            ),
            EdgeConnectionFailedError,
        ),
        (
            requests.ConnectTimeout(
                MaxRetryError(pool=POOL, url="/", reason=ConnectTimeoutError("timed out"))
            ),
            EdgeConnectionFailedError,
        ),
        (
            requests.exceptions.SSLError(
                MaxRetryError(pool=POOL, url="/", reason=SSLError("eof after sending"))
            ),
            EdgeOutcomeUnknownError,
        ),
        (requests.ConnectionError(ProtocolError("connection aborted")), EdgeOutcomeUnknownError),
        (requests.ReadTimeout("read timed out"), EdgeOutcomeUnknownError),
        (requests.exceptions.InvalidHeader("bad header value"), EdgeRejectedRequestError),
    ],
)
def test_a_transport_failure_maps_to_not_sent_connection_failed_or_outcome_unknown(
    monkeypatch: pytest.MonkeyPatch,
    settings: EdgeSettings,
    error: requests.RequestException,
    expected: type[RedisEnterpriseServicesError],
) -> None:
    with pytest.raises(expected_exception=expected):
        send_through_relay_answering(settings=settings, relay_outcome=error, monkeypatch=monkeypatch)


def test_every_call_goes_to_the_one_nginx_address_with_the_network_in_a_header(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings
) -> None:
    sent: list[tuple[object, object]] = []

    def fake_post(*, url: object, headers: dict[str, str], **_: object) -> requests.Response:
        sent.append((url, headers.get(settings.headers.network)))
        return relay_response(status_code=200, headers={})

    monkeypatch.setattr(target=requests, name="post", value=fake_post)
    EdgeClient(
        settings=settings,
        header_builder=EdgeHeaderBuilder(settings=settings),
        response_reader=EdgeResponseReader(settings=settings),
    ).send(network=NETWORK, request=REQUEST)

    assert sent == [(settings.url, NETWORK)]


def test_the_relay_body_stays_out_of_the_error_message(
    monkeypatch: pytest.MonkeyPatch, settings: EdgeSettings
) -> None:
    rejected: requests.Response = relay_response(
        status_code=502,
        headers={settings.headers.edge_error_code: settings.error_codes.response_rejected},
        body=b'{"error": "response_rejected", "reason": ["the-relay-explanation"]}',
    )

    with pytest.raises(expected_exception=EdgeRejectedResponseError) as error:
        send_through_relay_answering(settings=settings, relay_outcome=rejected, monkeypatch=monkeypatch)

    assert "the-relay-explanation" not in error.value.message
