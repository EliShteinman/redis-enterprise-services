import pytest
from pydantic import ValidationError

from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.remaining_resource import RemainingResource

GUID: str = "d71cefce-4e31-41fd-b654-37cbb2f39a01"
CLUSTER: dict[str, object] = {
    "cluster": "cluster-a",
    "cluster_url": "https://cluster-a.net-a:9443",
    "network": "net-a",
    "site": "dc1",
    "environment": "PROD",
    "access": {
        "endpoints": [{"dns_name": "redis-12000.cluster-a.net-a", "port": 12000, "addr": ["10.0.0.5"]}]
    },
    "db": {"db_uid": 7, "settings": {}, "permissions": []},
}
CRDB: dict[str, object] = {
    "default_db_config": {},
    "causal_consistency": False,
    "encryption": False,
    "featureset_version": None,
    "protocol_version": None,
    "instances": [{"cluster_url": "https://cluster-a.net-a:9443", "instance_id": 1, "compression": 3}],
}


@pytest.mark.parametrize(
    argnames=("active_active", "crdb_guid", "crdb"),
    argvalues=[(True, None, CRDB), (True, GUID, None), (False, GUID, None), (False, None, CRDB)],
)
def test_a_database_result_whose_active_active_fields_disagree_is_refused(
    active_active: bool, crdb_guid: str | None, crdb: dict[str, object] | None
) -> None:
    with pytest.raises(expected_exception=ValidationError):
        DatabaseResult.model_validate(
            {
                "name": "orders",
                "memory_size": 1,
                "active_active": active_active,
                "crdb_guid": crdb_guid,
                "crdb": crdb,
                "clusters": [CLUSTER],
            }
        )


def test_a_single_site_result_with_two_clusters_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        DatabaseResult.model_validate(
            {
                "name": "orders",
                "memory_size": 1,
                "active_active": False,
                "crdb_guid": None,
                "crdb": None,
                "clusters": [CLUSTER, CLUSTER],
            }
        )


@pytest.mark.parametrize(
    argnames=("resource_type", "uid", "crdb_guid"),
    argvalues=[("user", None, GUID), ("crdb", 5, None), ("permissions", 7, GUID)],
)
def test_a_remaining_resource_with_an_id_its_type_cannot_have_is_refused(
    resource_type: str, uid: int | None, crdb_guid: str | None
) -> None:
    with pytest.raises(expected_exception=ValidationError):
        RemainingResource.model_validate(
            {
                "cluster_url": "https://cluster-a.net-a:9443",
                "resource_type": resource_type,
                "name": "orders",
                "uid": uid,
                "crdb_guid": crdb_guid,
                "last_error": None,
            }
        )
