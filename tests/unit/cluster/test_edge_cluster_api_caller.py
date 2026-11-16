from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.edge_cluster_api_caller import EdgeClusterApiCaller
from redis_enterprise_services.cluster.edge_transport import EdgeTransport
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.edge.models import ClusterResponse
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError
from redis_enterprise_services.exceptions.edge import EdgeOutcomeUnknownError

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


@pytest.fixture
def cluster_api_settings(config_dir: Path) -> ClusterApiSettings:
    return load_settings(config_dir=config_dir).cluster_api


def test_a_cluster_rejection_keeps_the_cluster_status_and_error_code(
    cluster_api_settings: ClusterApiSettings,
) -> None:
    transport: MagicMock = create_autospec(spec=EdgeTransport, instance=True)
    transport.send.return_value = ClusterResponse(
        status_code=409, headers={}, body={"error_code": "name_already_exists"}, cluster_state_id=None
    )

    with pytest.raises(expected_exception=ClusterRejectedRequestError) as rejection:
        EdgeClusterApiCaller(edge_transport=transport, settings=cluster_api_settings).send(
            target=TARGET, method="POST", path="/v1/users"
        )

    assert (rejection.value.cluster_status_code, rejection.value.cluster_error_code) == (
        409,
        "name_already_exists",
    )


def test_a_redirect_answer_is_a_cluster_rejection(cluster_api_settings: ClusterApiSettings) -> None:
    transport: MagicMock = create_autospec(spec=EdgeTransport, instance=True)
    transport.send.return_value = ClusterResponse(
        status_code=302, headers={}, body=None, cluster_state_id=None
    )

    with pytest.raises(expected_exception=ClusterRejectedRequestError):
        EdgeClusterApiCaller(edge_transport=transport, settings=cluster_api_settings).send(
            target=TARGET, method="POST", path="/v1/users"
        )


def test_the_cluster_body_stays_out_of_the_rejection_message(
    cluster_api_settings: ClusterApiSettings,
) -> None:
    transport: MagicMock = create_autospec(spec=EdgeTransport, instance=True)
    transport.send.return_value = ClusterResponse(
        status_code=400,
        headers={},
        body={"error_code": "invalid_schema", "description": "the-echoed-value"},
        cluster_state_id=None,
    )

    with pytest.raises(expected_exception=ClusterRejectedRequestError) as rejection:
        EdgeClusterApiCaller(edge_transport=transport, settings=cluster_api_settings).send(
            target=TARGET, method="POST", path="/v1/bdbs"
        )

    assert "the-echoed-value" not in rejection.value.message


def test_an_error_on_the_way_to_the_cluster_names_that_cluster() -> None:
    transport: MagicMock = create_autospec(spec=EdgeTransport, instance=True)
    transport.send.side_effect = EdgeOutcomeUnknownError(message="no answer from the relay of local")

    with pytest.raises(expected_exception=EdgeOutcomeUnknownError) as failure:
        EdgeClusterApiCaller(edge_transport=transport, settings=load_settings().cluster_api).send(
            target=TARGET, method="GET", path="/v1/bdbs"
        )

    assert failure.value.cluster_url == "https://cluster.local:9443"


def test_a_cluster_refusal_names_the_cluster() -> None:
    transport: MagicMock = create_autospec(spec=EdgeTransport, instance=True)
    transport.send.return_value = ClusterResponse(
        status_code=404, headers={}, body=None, cluster_state_id=None
    )

    with pytest.raises(expected_exception=ClusterRejectedRequestError) as failure:
        EdgeClusterApiCaller(edge_transport=transport, settings=load_settings().cluster_api).send(
            target=TARGET, method="GET", path="/v1/bdbs/1"
        )

    assert failure.value.cluster_url == "https://cluster.local:9443"
