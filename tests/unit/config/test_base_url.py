import pytest
from pydantic import TypeAdapter, ValidationError

from redis_enterprise_services.config.base_url import BaseUrl


@pytest.mark.parametrize(
    argnames="url",
    argvalues=[
        "https:///x",
        "https://c1:9443?x=1",
        "https://c1:9443#top",
        "https://c1:port",
        "https://c1:99999",
        "https://c1:0",
    ],
)
def test_a_base_url_with_no_host_a_query_a_fragment_or_a_bad_port_is_refused(url: str) -> None:
    with pytest.raises(expected_exception=ValidationError):
        TypeAdapter(BaseUrl).validate_python(url)
