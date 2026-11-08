from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ClusterRequestError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_request_error"
    status_code: ClassVar[int] = HTTPStatus.BAD_GATEWAY

    def __init__(self, *, message: str, cluster_status_code: int, cluster_error_code: str | None) -> None:
        super().__init__(message=message)
        self.cluster_status_code: int = cluster_status_code
        self.cluster_error_code = cluster_error_code


class DatabaseActivationTimeoutError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_activation_timeout"
    status_code: ClassVar[int] = HTTPStatus.GATEWAY_TIMEOUT


class UnrestorableFieldsError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "unrestorable_fields"


class DatabaseDeletionTimeoutError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_deletion_timeout"
    status_code: ClassVar[int] = HTTPStatus.GATEWAY_TIMEOUT


class DatabaseCreationFailedError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_creation_failed"
    status_code: ClassVar[int] = HTTPStatus.BAD_GATEWAY


class ClusterActionFailedError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_action_failed"
    status_code: ClassVar[int] = HTTPStatus.BAD_GATEWAY


class ClusterActionTimeoutError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_action_timeout"
    status_code: ClassVar[int] = HTTPStatus.GATEWAY_TIMEOUT


class AmbiguousResourceError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "ambiguous_resource"


class UnreadableClusterAnswerError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "unreadable_cluster_answer"
    status_code: ClassVar[int] = HTTPStatus.BAD_GATEWAY
