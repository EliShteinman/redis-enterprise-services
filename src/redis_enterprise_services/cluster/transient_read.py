from http import HTTPStatus

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import ClusterRequestError
from redis_enterprise_services.exceptions.edge import OutcomeUnknownError, RequestNotSentError


def worth_reading_again(*, error: RedisEnterpriseServicesError, transient_codes: frozenset[str]) -> bool:
    if isinstance(error, (RequestNotSentError, OutcomeUnknownError)):
        return True
    if isinstance(error, ClusterRequestError):
        server_failed: bool = error.cluster_status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        return server_failed or error.error_code in transient_codes
    return False
