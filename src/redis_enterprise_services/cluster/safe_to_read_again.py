from http import HTTPStatus

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError
from redis_enterprise_services.exceptions.edge import EdgeConnectionFailedError, EdgeOutcomeUnknownError


def is_safe_to_read_again(
    *, error: RedisEnterpriseServicesError, transient_error_codes: frozenset[str]
) -> bool:
    if isinstance(error, (EdgeConnectionFailedError, EdgeOutcomeUnknownError)):
        return True
    if isinstance(error, ClusterRejectedRequestError):
        server_failed: bool = error.cluster_status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        return server_failed or has_transient_error_code(
            error=error, transient_error_codes=transient_error_codes
        )
    return False


def has_transient_error_code(
    *, error: ClusterRejectedRequestError, transient_error_codes: frozenset[str]
) -> bool:
    return error.cluster_error_code in transient_error_codes
