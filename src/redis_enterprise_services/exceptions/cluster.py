from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ClusterRejectedRequestError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_rejected_request"

    def __init__(self, *, message: str, cluster_status_code: int, cluster_error_code: str | None) -> None:
        super().__init__(message=message)
        self.cluster_status_code: int = cluster_status_code
        self.cluster_error_code: str | None = cluster_error_code


class DatabaseActivationTimeoutError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_activation_timeout"


class UnrestorableFieldsError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "unrestorable_fields"


class DatabaseDeletionTimeoutError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_deletion_timeout"


class DatabaseCreationFailedError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_creation_failed"


class ClusterActionFailedError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_action_failed"


class ClusterActionTimeoutError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_action_timeout"


class DuplicateResourceNameError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "duplicate_resource_name"


class UnreadableClusterResponseError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "unreadable_cluster_response"
