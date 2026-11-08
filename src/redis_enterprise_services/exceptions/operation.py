from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class OperationNotFoundError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "operation_not_found"
    status_code: ClassVar[int] = HTTPStatus.NOT_FOUND
