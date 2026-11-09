import pytest
from pydantic import ValidationError

from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.remaining_resource import RemainingResource

ERROR: PublicError = PublicError(code="internal_error", message="internal error")


@pytest.mark.parametrize(
    argnames=("status", "error"),
    argvalues=[
        (OperationStatus.SUCCEEDED, ERROR),
        (OperationStatus.RUNNING, ERROR),
        (OperationStatus.ROLLED_BACK, None),
        (OperationStatus.REJECTED, None),
        (OperationStatus.REQUIRES_MANUAL_INTERVENTION, None),
    ],
)
def test_an_error_that_does_not_fit_the_status_is_refused(
    status: OperationStatus, error: PublicError | None
) -> None:
    with pytest.raises(expected_exception=ValidationError):
        Operation(trace_id="trace-1", status=status, error=error)


DATABASE: DatabaseResult = DatabaseResult.model_validate(
    {
        "name": "orders",
        "memory_size": 1,
        "active_active": False,
        "crdb_guid": None,
        "clusters": [
            {
                "cluster_url": "https://c:9443",
                "network": "n",
                "site": "s",
                "environment": "DEV",
                "access": {"endpoints": [{"dns_name": "d", "port": 1, "addr": []}]},
                "db": {"db_uid": 1, "settings": {}, "permissions": []},
            }
        ],
    }
)
REMAINING: RemainingResource = RemainingResource(
    cluster_url="https://c1:9443", resource_type="acl", name="orders-app", uid=None, last_error=None
)


@pytest.mark.parametrize(
    argnames="operation_fields",
    argvalues=[
        pytest.param(
            {"status": OperationStatus.ROLLED_BACK, "error": ERROR, "database": DATABASE}, id="database"
        ),
        pytest.param(
            {"status": OperationStatus.REJECTED, "error": ERROR, "not_rolled_back": []},
            id="remaining-on-rejected",
        ),
        pytest.param(
            {"status": OperationStatus.ROLLED_BACK, "error": ERROR, "not_rolled_back": [REMAINING]},
            id="remaining-on-rolled-back",
        ),
    ],
)
def test_a_field_that_does_not_fit_the_status_is_refused(operation_fields: dict[str, object]) -> None:
    with pytest.raises(expected_exception=ValidationError):
        Operation.model_validate(obj={"trace_id": "trace-1", **operation_fields})
