import logging
from typing import Annotated
from urllib.parse import SplitResult, urlsplit

from pydantic import AfterValidator, Field

logger: logging.Logger = logging.getLogger(name=__name__)

DEFAULT_PORT_BY_SCHEME: dict[str, int] = {"http": 80, "https": 443}
NO_PORT: int = 0


def reject_an_invalid_port(url: str) -> str:
    try:
        port: int | None = urlsplit(url).port
    except ValueError as error:
        raise ValueError(f"{url} has an invalid port: {error}") from error
    if port == NO_PORT:
        raise ValueError(f"{url} has port {NO_PORT}, which nothing listens on")
    logger.debug(msg=f"{url} uses port {port or 'the scheme default'}")
    return url


def reject_a_missing_host(url: str) -> str:
    if not urlsplit(url).hostname:
        raise ValueError(f"{url} has no host")
    return url


type BaseUrl = Annotated[
    str,
    Field(pattern=r"^https?://[^/\s?#]+(/[^\s?#]*[^/\s?#])?$"),
    AfterValidator(reject_an_invalid_port),
    AfterValidator(reject_a_missing_host),
]
type RelayUrl = Annotated[
    str,
    Field(pattern=r"^https?://[^/\s?#]+(/[^\s?#]*)?$"),
    AfterValidator(reject_an_invalid_port),
    AfterValidator(reject_a_missing_host),
]


def comparable_url(*, url: str) -> str:
    parts: SplitResult = urlsplit(url)
    scheme: str = parts.scheme.lower()
    port: int = DEFAULT_PORT_BY_SCHEME[scheme] if parts.port is None else parts.port
    return f"{scheme}://{(parts.hostname or '').lower()}:{port}{parts.path}"
