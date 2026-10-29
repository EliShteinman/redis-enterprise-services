from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.edge.models import ClusterCredentials, ClusterResponse
from redis_enterprise_services.exceptions.cluster import UnreadableAnswerError

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


def test_an_answer_without_a_cluster_state_id_is_unreadable() -> None:
    api: MagicMock = create_autospec(spec=ClusterApi, instance=True)
    api.send.return_value = ClusterResponse(
        status_code=200, headers={}, body={"memory_size": 100}, cluster_state_id=None
    )
    repository: DatabaseRepository = DatabaseRepository(
        api=api, settings=load_settings().database, cluster=load_settings().cluster
    )

    with pytest.raises(expected_exception=UnreadableAnswerError):
        repository.get_fields(target=TARGET, uid=1, fields=["memory_size"])
