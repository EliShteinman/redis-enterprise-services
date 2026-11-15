from typing import Annotated
from urllib.parse import SplitResult, urlsplit

from pydantic import AfterValidator, Field

DEFAULT_PORT_BY_SCHEME: dict[str, int] = {"http": 80, "https": 443}
NO_PORT: int = 0


def reject_an_invalid_port(url: str) -> str:
    try:
        port: int | None = urlsplit(url).port
    except ValueError as error:
        raise ValueError(f"the URL has an invalid port: {error}") from error
    if port == NO_PORT:
        raise ValueError(f"the URL has port {NO_PORT}, which nothing listens on")
    return url


def reject_a_missing_host(url: str) -> str:
    if not urlsplit(url).hostname:
        raise ValueError("the URL has no host")
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
    if parts.port is None and scheme not in DEFAULT_PORT_BY_SCHEME:
        raise ValueError(f"a URL with scheme {scheme!r} and no port cannot be compared")
    port: int = DEFAULT_PORT_BY_SCHEME[scheme] if parts.port is None else parts.port
    return f"{scheme}://{(parts.hostname or '').lower()}:{port}{parts.path}"
