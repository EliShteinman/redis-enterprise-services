import pytest
from pydantic import TypeAdapter, ValidationError

from redis_enterprise_services.config.item_path import ItemPath


@pytest.mark.parametrize(
    argnames="path", argvalues=["/v1/bdbs", "/v1/bdbs/{id}", "/v1/bdbs/{uid}/{uid2}", "v1/bdbs/{uid}"]
)
def test_an_item_path_not_rooted_or_without_exactly_the_uid_placeholder_is_refused(path: str) -> None:
    with pytest.raises(expected_exception=ValidationError):
        TypeAdapter(ItemPath).validate_python(path)
