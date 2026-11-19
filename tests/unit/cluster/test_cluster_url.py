import pytest

from redis_enterprise_services.cluster.cluster_url import cluster_url


@pytest.mark.parametrize(
    argnames=("query_string", "expected"),
    argvalues=[
        (None, "https://c1:9443/v1/bdbs/1"),
        ("fields=uid,name", "https://c1:9443/v1/bdbs/1?fields=uid,name"),
    ],
)
def test_the_cluster_url_is_the_api_url_and_path_with_the_query_string_when_given(
    query_string: str | None, expected: str
) -> None:
    assert cluster_url(api_url="https://c1:9443", path="/v1/bdbs/1", query_string=query_string) == expected
