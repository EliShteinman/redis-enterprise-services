from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.transport import EdgeTransport
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.connection.models import ClusterCredentials
from redis_enterprise_services.edge.models import ClusterResponse
from redis_enterprise_services.exceptions.cluster import ClusterRequestError

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


def test_a_cluster_error_answer_keeps_the_cluster_status_and_error_code() -> None:
    transport: MagicMock = create_autospec(spec=EdgeTransport, instance=True)
    transport.send.return_value = ClusterResponse(
        status_code=409, headers={}, body={"error_code": "name_already_exists"}, cluster_state_id=None
    )

    with pytest.raises(expected_exception=ClusterRequestError) as rejection:
        ClusterApi(transport=transport, settings=load_settings().cluster).send(
            target=TARGET, method="POST", path="/v1/users"
        )

    assert (rejection.value.cluster_status_code, rejection.value.error_code) == (409, "name_already_exists")
