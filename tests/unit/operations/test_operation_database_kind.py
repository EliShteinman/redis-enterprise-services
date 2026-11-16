import pytest
from pydantic import ValidationError

from redis_enterprise_services.operations.active_active_database_result import ActiveActiveDatabaseResult
from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.operation import Operation

CLUSTER: dict[str, object] = {
    "cluster": "cluster-a.net-a",
    "cluster_url": "https://cluster-a.net-a:9443",
    "network": "net-a",
    "site": "NY",
    "environment": "PROD",
    "access": {
        "endpoints": [{"dns_name": "redis-12000.cluster-a.net-a", "port": 12000, "addr": ["10.0.0.5"]}]
    },
    "db": {"db_uid": 7, "settings": {}, "permissions": []},
}
CRDB: dict[str, object] = {
    "guid": "d71cefce-4e31-41fd-b654-37cbb2f39a01",
    "causal_consistency": False,
    "encryption": False,
    "featureset_version": 12,
    "protocol_version": 1,
    "default_db_config": {},
}
SINGLE_SITE: dict[str, object] = {
    "kind": "single_site",
    "name": "orders",
    "memory_size": 1,
    "cluster": CLUSTER,
}
ACTIVE_ACTIVE: dict[str, object] = {
    "kind": "active_active",
    "name": "orders",
    "memory_size": 1,
    "crdb": CRDB,
    "clusters": [{**CLUSTER, "instance_id": 1, "compression": 3}],
}


def succeeded_operation(*, database: dict[str, object]) -> Operation:
    return Operation.model_validate({"trace_id": "trace-1", "status": "succeeded", "database": database})


@pytest.mark.parametrize(
    argnames=("database", "result_model"),
    argvalues=[
        pytest.param(SINGLE_SITE, DatabaseResult, id="single_site"),
        pytest.param(ACTIVE_ACTIVE, ActiveActiveDatabaseResult, id="active_active"),
    ],
)
def test_the_kind_of_a_database_chooses_its_result_model(
    database: dict[str, object], result_model: type[DatabaseResult | ActiveActiveDatabaseResult]
) -> None:
    assert isinstance(succeeded_operation(database=database).database, result_model)


def test_a_database_of_one_kind_in_the_shape_of_the_other_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        succeeded_operation(database={**ACTIVE_ACTIVE, "kind": "single_site"})


def test_an_active_active_result_without_clusters_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        succeeded_operation(database={**ACTIVE_ACTIVE, "clusters": []})
