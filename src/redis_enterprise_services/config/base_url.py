from typing import Annotated
from urllib.parse import SplitResult, urlsplit

from pydantic import Field

type BaseUrl = Annotated[str, Field(pattern=r"^https?://[^/\s]+(/\S*[^/\s])?$")]

DEFAULT_PORT_BY_SCHEME: dict[str, int] = {"http": 80, "https": 443}


def comparable_url(*, url: str) -> str:
    parts: SplitResult = urlsplit(url)
    scheme: str = parts.scheme.lower()
    port: int = parts.port or DEFAULT_PORT_BY_SCHEME[scheme]
    return f"{scheme}://{(parts.hostname or '').lower()}:{port}{parts.path}"
