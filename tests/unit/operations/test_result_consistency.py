import pytest
from pydantic import ValidationError

from redis_enterprise_services.operations.remaining_resource import RemainingResource

GUID: str = "d71cefce-4e31-41fd-b654-37cbb2f39a01"


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
