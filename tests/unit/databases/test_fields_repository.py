from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.databases.fields_repository import DatabaseFieldsRepository
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


def test_an_answer_without_a_cluster_state_id_is_unreadable() -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body={"memory_size": 100}, cluster_state_id=None)
    settings: Settings = load_settings()
    repository: DatabaseFieldsRepository = DatabaseFieldsRepository(
        api=api, settings=settings.database, cluster_api=settings.cluster_api
    )

    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        repository.get_fields(target=TARGET, uid=1, fields=["memory_size"])
