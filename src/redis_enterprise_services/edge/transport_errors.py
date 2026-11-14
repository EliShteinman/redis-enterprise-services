import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.edge import (
    EdgeConnectionFailedError,
    EdgeOutcomeUnknownError,
    EdgeRejectedRequestError,
)

NOT_SENT_REQUEST_ERRORS: tuple[type[requests.RequestException], ...] = (
    requests.exceptions.InvalidURL,
    requests.exceptions.InvalidHeader,
    requests.exceptions.MissingSchema,
    requests.exceptions.InvalidSchema,
)


def failed_to_connect_to_relay(*, error: requests.RequestException) -> bool:
    return any(
        isinstance(argument, MaxRetryError)
        and isinstance(argument.reason, (ConnectTimeoutError, NewConnectionError))
        for argument in error.args
    )


def edge_error_for_transport_failure(
    *, network: str, error: requests.RequestException
) -> RedisEnterpriseServicesError:
    if isinstance(error, NOT_SENT_REQUEST_ERRORS):
        return EdgeRejectedRequestError(message=f"the request to the relay of {network} is invalid")
    if failed_to_connect_to_relay(error=error):
        return EdgeConnectionFailedError(message=f"the relay of {network} is unreachable")
    return EdgeOutcomeUnknownError(message=f"no answer from the relay of {network}")
