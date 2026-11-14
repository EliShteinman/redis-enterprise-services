import pytest

from redis_enterprise_services.crdbs.models import Crdb
from redis_enterprise_services.exceptions.cluster import IncompleteClusterObjectError
from redis_enterprise_services.steps.find_local_crdb_instance import local_instance


def crdb_with(*, db_uid: str | None) -> Crdb:
    return Crdb.model_validate(
        obj={
            "guid": "g",
            "name": "orders",
            "default_db_config": {},
            "instances": [{"id": 1, "cluster": {"url": "https://cluster-a:9443"}, "db_uid": db_uid}],
        }
    )


@pytest.mark.parametrize(argnames="db_uid", argvalues=[None, "", "not-a-number"])
def test_a_crdb_without_a_readable_local_database_uid_is_incomplete(db_uid: str | None) -> None:
    with pytest.raises(expected_exception=IncompleteClusterObjectError):
        local_instance(crdb=crdb_with(db_uid=db_uid), api_url="https://cluster-a:9443")
