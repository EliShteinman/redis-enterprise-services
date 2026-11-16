from http import HTTPStatus

from pydantic import BaseModel

from redis_enterprise_services.api.rejections.rejection_error import RejectionError
from redis_enterprise_services.api.rejections.rejection_error_code import RejectionErrorCode
from redis_enterprise_services.config.public_errors.error_kind import ErrorKind
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.errors.public_errors import INTERNAL_ERROR_CODE


class ServiceRejection(BaseModel):
    status_code: int
    error: RejectionError


def service_rejection(
    *,
    error: RedisEnterpriseServicesError,
    public_code: RejectionErrorCode,
    kind: ErrorKind,
    internal_error_message: str,
) -> ServiceRejection:
    if public_code == INTERNAL_ERROR_CODE:
        return ServiceRejection(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            error=RejectionError(code=public_code, kind=kind, message=internal_error_message),
        )
    return ServiceRejection(
        status_code=error.status_code,
        error=RejectionError(code=public_code, kind=kind, message=error.message),
    )
