from typing import Annotated
from urllib.parse import SplitResult, urlsplit

from pydantic import AfterValidator, SecretStr

REDIS_SCHEMES: tuple[str, ...] = ("redis", "rediss")


def reject_a_non_redis_url(url: SecretStr) -> SecretStr:
    try:
        parts: SplitResult = urlsplit(url.get_secret_value())
        port: int | None = parts.port
    except ValueError as error:
        raise ValueError("the connection string is not a valid URL") from error
    if parts.scheme not in REDIS_SCHEMES:
        raise ValueError("the connection string must start with redis:// or rediss://")
    if not parts.hostname:
        raise ValueError("the connection string has no host")
    if port == 0:
        raise ValueError("the connection string has port 0, which nothing listens on")
    return url


type RedisConnectionUrl = Annotated[SecretStr, AfterValidator(reject_a_non_redis_url)]
