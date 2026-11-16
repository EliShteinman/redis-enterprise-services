import re

import pytest

from redis_enterprise_services.telemetry.excluded_urls import excluded_urls


@pytest.mark.parametrize(
    argnames=("url", "excluded"),
    argvalues=[
        ("http://pod:8080/health", True),
        ("https://service.example/health", True),
        ("http://pod:8080/health/x", False),
        ("http://pod:8080/v1/health", False),
        ("http://pod:8080/v1/databases", False),
    ],
)
def test_only_quiet_paths_are_left_out_of_tracing(url: str, excluded: bool) -> None:
    patterns: list[str] = excluded_urls(paths=frozenset({"/health"})).split(",")

    assert any(re.search(pattern=pattern, string=url) for pattern in patterns) == excluded
