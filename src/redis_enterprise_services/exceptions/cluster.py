from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ClusterRejectedRequestError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_rejected_request"
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


class DuplicateResourceNameError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "duplicate_resource_name"


class UnreadableClusterResponseError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "unreadable_cluster_response"
    status_code: ClassVar[int] = HTTPStatus.BAD_GATEWAY
