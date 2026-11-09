import pytest
from pydantic import ValidationError

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError

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
