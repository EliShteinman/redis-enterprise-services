from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ClusterRequestError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_error"
    status_code: ClassVar[int] = HTTPStatus.BAD_GATEWAY

    def __init__(self, *, message: str, cluster_status_code: int, error_code: str | None) -> None:
        super().__init__(message=message)
        self.cluster_status_code: int = cluster_status_code
        self.error_code: str | None = error_code


class DatabaseNotActiveError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_not_active"
    status_code: ClassVar[int] = HTTPStatus.GATEWAY_TIMEOUT
