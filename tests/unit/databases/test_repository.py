from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.caller import ClusterCaller
from redis_enterprise_services.cluster.models import ClusterAnswer, ClusterTarget
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.edge.models import ClusterCredentials
from redis_enterprise_services.exceptions.cluster import UnreadableAnswerError

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


def test_an_answer_without_a_cluster_state_id_is_unreadable() -> None:
    api: MagicMock = create_autospec(spec=ClusterCaller, instance=True)
    api.send.return_value = ClusterAnswer(body={"memory_size": 100}, cluster_state_id=None)
    settings: Settings = load_settings()
    repository: DatabaseRepository = DatabaseRepository(
        api=api, settings=settings.database, cluster=settings.cluster
    )

    with pytest.raises(expected_exception=UnreadableAnswerError):
        repository.get_fields(target=TARGET, uid=1, fields=["memory_size"])
