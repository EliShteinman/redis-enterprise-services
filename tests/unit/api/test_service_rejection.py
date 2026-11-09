from http import HTTPStatus

from redis_enterprise_services.api.rejection_error_code import RejectionErrorCode
from redis_enterprise_services.api.service_rejection import ServiceRejection, service_rejection
from redis_enterprise_services.exceptions.planning import InvalidNameError

INTERNAL_ERROR_MESSAGE: str = "internal error"


def rejection_of(*, public_code: RejectionErrorCode) -> ServiceRejection:
    return service_rejection(
        error=InvalidNameError(message="the name is invalid"),
        public_code=public_code,
        internal_error_message=INTERNAL_ERROR_MESSAGE,
    )


def test_an_internal_error_is_answered_with_500_and_the_generic_message() -> None:
    rejection: ServiceRejection = rejection_of(public_code="internal_error")

    assert (rejection.status_code, rejection.error.message) == (
        HTTPStatus.INTERNAL_SERVER_ERROR,
        INTERNAL_ERROR_MESSAGE,
    )


def test_a_public_error_keeps_its_own_status_and_message() -> None:
    rejection: ServiceRejection = rejection_of(public_code="invalid_name")

    assert (rejection.status_code, rejection.error.message) == (
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "the name is invalid",
    )
