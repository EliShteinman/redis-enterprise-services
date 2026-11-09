import pytest

from redis_enterprise_services.config.user_resources_settings import (
    reject_template_without_database_user_placeholders,
)


@pytest.mark.parametrize(
    argnames="template", argvalues=["{user}-{database}-acl", "{database}{user}", "{database}-acl"]
)
def test_a_template_that_does_not_name_database_then_user_is_refused(template: str) -> None:
    with pytest.raises(expected_exception=ValueError):
        reject_template_without_database_user_placeholders(template)


def test_a_template_that_joins_database_and_user_is_accepted() -> None:
    assert (
        reject_template_without_database_user_placeholders("{database}-{user}-acl") == "{database}-{user}-acl"
    )
