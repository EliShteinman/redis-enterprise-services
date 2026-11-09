import logging
from typing import Annotated
from urllib.parse import SplitResult, urlsplit

from pydantic import AfterValidator, Field

logger: logging.Logger = logging.getLogger(name=__name__)

DEFAULT_PORT_BY_SCHEME: dict[str, int] = {"http": 80, "https": 443}


def reject_an_invalid_port(url: str) -> str:
    try:
        port: int | None = urlsplit(url).port
    except ValueError as error:
        raise ValueError(f"{url} has an invalid port: {error}") from error
    logger.debug(msg=f"{url} uses port {port or 'the scheme default'}")
    return url


type BaseUrl = Annotated[
    str, Field(pattern=r"^https?://[^/\s?#]+(/[^\s?#]*[^/\s?#])?$"), AfterValidator(reject_an_invalid_port)
]
type RelayUrl = Annotated[
    str, Field(pattern=r"^https?://[^/\s?#]+(/[^\s?#]*)?$"), AfterValidator(reject_an_invalid_port)
]


def comparable_url(*, url: str) -> str:
    parts: SplitResult = urlsplit(url)
    scheme: str = parts.scheme.lower()
    port: int = parts.port or DEFAULT_PORT_BY_SCHEME[scheme]
    return f"{scheme}://{(parts.hostname or '').lower()}:{port}{parts.path}"
