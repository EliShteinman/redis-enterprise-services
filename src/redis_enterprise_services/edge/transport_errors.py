import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError

from redis_enterprise_services.exceptions.edge import (
    EdgeConnectionFailedError,
    EdgeError,
    EdgeOutcomeUnknownError,
)


def never_reached_relay(*, error: requests.RequestException) -> bool:
    return any(
        isinstance(argument, MaxRetryError)
        and isinstance(argument.reason, (ConnectTimeoutError, NewConnectionError))
        for argument in error.args
    )


def edge_error_for_transport_failure(*, network: str, error: requests.RequestException) -> EdgeError:
    if never_reached_relay(error=error):
        return EdgeConnectionFailedError(message=f"the relay of {network} is unreachable: {error}")
    return EdgeOutcomeUnknownError(message=f"no answer from the relay of {network}: {error}")
