from redis_enterprise_services.cluster.rejection_kind import has_transient_error_code, is_server_failure
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError
from redis_enterprise_services.exceptions.edge import EdgeConnectionFailedError, EdgeOutcomeUnknownError


def is_safe_to_read_again(
    *, error: RedisEnterpriseServicesError, transient_error_codes: frozenset[str]
) -> bool:
    if isinstance(error, (EdgeConnectionFailedError, EdgeOutcomeUnknownError)):
        return True
    if isinstance(error, ClusterRejectedRequestError):
        return is_server_failure(error=error) or has_transient_error_code(
            error=error, transient_error_codes=transient_error_codes
        )
    return False
