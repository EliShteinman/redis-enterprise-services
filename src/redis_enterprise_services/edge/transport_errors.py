import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.edge import (
    EdgeOutcomeUnknownError,
    EdgeRejectedRequestError,
    EdgeUnreachableError,
)

NOT_SENT_REQUEST_ERRORS: tuple[type[requests.RequestException], ...] = (
    requests.exceptions.InvalidURL,
    requests.exceptions.InvalidHeader,
    requests.exceptions.MissingSchema,
    requests.exceptions.InvalidSchema,
)


def failed_to_connect_to_edge_proxy(*, error: requests.RequestException) -> bool:
    return any(
        isinstance(argument, MaxRetryError)
        and isinstance(argument.reason, (ConnectTimeoutError, NewConnectionError))
        for argument in error.args
    )


def edge_error_for_transport_failure(
    *, network: str, error: requests.RequestException
) -> RedisEnterpriseServicesError:
    if isinstance(error, NOT_SENT_REQUEST_ERRORS):
        return EdgeRejectedRequestError(message=f"the request to the edge proxy for {network} is invalid")
    if failed_to_connect_to_edge_proxy(error=error):
        return EdgeUnreachableError(message=f"the edge proxy is unreachable, nothing was sent to {network}")
    return EdgeOutcomeUnknownError(message=f"no answer from the relay of {network}")
