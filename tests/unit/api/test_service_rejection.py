from http import HTTPStatus

import pytest

from redis_enterprise_services.api.rejection_error_code import RejectionErrorCode
from redis_enterprise_services.api.service_rejection import ServiceRejection, service_rejection
from redis_enterprise_services.exceptions.planning import InvalidNameError

INTERNAL_ERROR_MESSAGE: str = "internal error"


@pytest.mark.parametrize(
    argnames=("public_code", "expected_status", "expected_message"),
    argvalues=[
        ("internal_error", HTTPStatus.INTERNAL_SERVER_ERROR, INTERNAL_ERROR_MESSAGE),
        ("invalid_name", HTTPStatus.UNPROCESSABLE_CONTENT, "the name is invalid"),
    ],
)
def test_an_internal_error_is_answered_with_500_and_the_generic_message(
    public_code: RejectionErrorCode, expected_status: int, expected_message: str
) -> None:
    rejection: ServiceRejection = service_rejection(
        error=InvalidNameError(message="the name is invalid"),
        public_code=public_code,
        internal_error_message=INTERNAL_ERROR_MESSAGE,
    )

    assert (rejection.status_code, rejection.error.message) == (expected_status, expected_message)
