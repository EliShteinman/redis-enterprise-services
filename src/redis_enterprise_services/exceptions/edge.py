from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class EdgeError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_unavailable"
    status_code: ClassVar[int] = HTTPStatus.BAD_GATEWAY


class InvalidEdgeRequestError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "internal_error"
    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR


class EdgeRequestNotSentError(EdgeError):
    pass


class EdgeOutcomeUnknownError(EdgeError):
    pass


class InvalidClusterResponseError(EdgeError):
    def __init__(self, *, message: str, cluster_status_code: int | None) -> None:
        super().__init__(message=message)
        self.cluster_status_code: int | None = cluster_status_code
