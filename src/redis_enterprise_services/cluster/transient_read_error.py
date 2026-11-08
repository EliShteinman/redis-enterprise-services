from http import HTTPStatus

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError
from redis_enterprise_services.exceptions.edge import EdgeOutcomeUnknownError, EdgeRequestNotSentError


def is_transient_read_error(
    *, error: RedisEnterpriseServicesError, transient_error_codes: frozenset[str]
) -> bool:
    if isinstance(error, (EdgeRequestNotSentError, EdgeOutcomeUnknownError)):
        return True
    if isinstance(error, ClusterRejectedRequestError):
        server_failed: bool = error.cluster_status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        return server_failed or error.cluster_error_code in transient_error_codes
    return False
