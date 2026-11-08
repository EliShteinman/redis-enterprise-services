from http import HTTPStatus

from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError


def is_server_failure(*, error: ClusterRejectedRequestError) -> bool:
    return error.cluster_status_code >= HTTPStatus.INTERNAL_SERVER_ERROR


def is_not_found(*, error: ClusterRejectedRequestError) -> bool:
    return error.cluster_status_code == HTTPStatus.NOT_FOUND


def has_transient_error_code(
    *, error: ClusterRejectedRequestError, transient_error_codes: frozenset[str]
) -> bool:
    return error.cluster_error_code in transient_error_codes
