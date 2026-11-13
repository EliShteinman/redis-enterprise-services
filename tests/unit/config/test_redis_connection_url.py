import pytest
from pydantic import SecretStr, TypeAdapter, ValidationError

from redis_enterprise_services.config.redis_connection_url import RedisConnectionUrl


@pytest.mark.parametrize(
    argnames="url",
    argvalues=[
        "http://saga:secret@state:12005",
        "redis://saga:secret@:12005",
        "redis://saga:secret@state:0",
        "redis://saga:secret@state:99999",
    ],
)
def test_a_connection_string_that_is_not_a_reachable_redis_url_is_refused(url: str) -> None:
    with pytest.raises(expected_exception=ValidationError):
        TypeAdapter(RedisConnectionUrl).validate_python(url)


@pytest.mark.parametrize(
    argnames="url", argvalues=["redis://saga:secret@state:12005", "rediss://saga:secret@state:12005"]
)
def test_a_redis_connection_string_is_kept_secret(url: str) -> None:
    assert TypeAdapter(RedisConnectionUrl).validate_python(url) == SecretStr(url)
