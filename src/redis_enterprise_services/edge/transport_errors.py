import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError

from redis_enterprise_services.exceptions.edge import EdgeError, OutcomeUnknownError, RequestNotSentError


def was_not_sent(*, error: requests.RequestException) -> bool:
    return any(
        isinstance(argument, MaxRetryError) and isinstance(argument.reason, ConnectTimeoutError)
        for argument in error.args
    )


def transport_error(*, network: str, error: requests.RequestException) -> EdgeError:
    if was_not_sent(error=error):
        return RequestNotSentError(message=f"the relay of {network} is unreachable: {error}")
    return OutcomeUnknownError(message=f"no answer from the relay of {network}: {error}")
