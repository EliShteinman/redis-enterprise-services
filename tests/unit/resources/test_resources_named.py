import pytest

from redis_enterprise_services.resources.models import NamedResource
from redis_enterprise_services.resources.resources_named import resources_named

RESOURCES: list[NamedResource] = [
    NamedResource(uid=1, name="Administrator"),
    NamedResource(uid=6, name="app-user"),
]


@pytest.mark.parametrize(
    argnames=("name", "expected"),
    argvalues=[
        ("app-user", [NamedResource(uid=6, name="app-user")]),
        ("no-such-user", []),
        ("APP-USER", []),
    ],
)
def test_only_resources_with_exactly_that_name_are_kept(name: str, expected: list[NamedResource]) -> None:
    assert resources_named(resources=RESOURCES, name=name) == expected
