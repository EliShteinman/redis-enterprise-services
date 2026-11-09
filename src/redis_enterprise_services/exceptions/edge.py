from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class EdgeError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "cluster_unavailable"


class EdgeRejectedRequestError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "edge_rejected_request"


class EdgeConnectionFailedError(EdgeError):
    code: ClassVar[str] = "edge_connection_failed"


class EdgeOutcomeUnknownError(EdgeError):
    code: ClassVar[str] = "edge_outcome_unknown"


class EdgeRejectedResponseError(EdgeError):
    code: ClassVar[str] = "edge_rejected_response"

    def __init__(self, *, message: str, cluster_status_code: int | None) -> None:
        super().__init__(message=message)
        self.cluster_status_code: int | None = cluster_status_code
