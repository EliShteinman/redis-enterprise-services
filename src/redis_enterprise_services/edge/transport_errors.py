import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError

from redis_enterprise_services.exceptions.edge import (
    EdgeError,
    EdgeOutcomeUnknownError,
    EdgeRequestNotSentError,
)


def was_not_sent(*, error: requests.RequestException) -> bool:
    return any(
        isinstance(argument, MaxRetryError)
        and isinstance(argument.reason, (ConnectTimeoutError, NewConnectionError))
        for argument in error.args
    )


def transport_error(*, network: str, error: requests.RequestException) -> EdgeError:
    if was_not_sent(error=error):
        return EdgeRequestNotSentError(message=f"the relay of {network} is unreachable: {error}")
    return EdgeOutcomeUnknownError(message=f"no answer from the relay of {network}: {error}")
