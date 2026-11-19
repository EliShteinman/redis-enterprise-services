import pytest

from redis_enterprise_services.cluster.models import SuccessfulClusterResponse
from redis_enterprise_services.databases.rest_database_fields_repository import fields_snapshot
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError


def test_an_answer_without_a_cluster_state_id_is_unreadable() -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        fields_snapshot(
            response=SuccessfulClusterResponse(body={"status": "active"}, cluster_state_id=None), uid=1
        )
