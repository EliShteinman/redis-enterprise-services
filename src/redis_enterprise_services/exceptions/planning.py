from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class UnknownClusterError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "unknown_cluster"
    status_code: ClassVar[int] = HTTPStatus.UNPROCESSABLE_ENTITY


class InvalidNameError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "invalid_name"
    status_code: ClassVar[int] = HTTPStatus.UNPROCESSABLE_ENTITY
