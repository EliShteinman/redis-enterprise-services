import pytest

from redis_enterprise_services.config.naming_settings import RedisNameRulesSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.planning.database_spec import DatabaseSpec, DatabaseUserSpec
from redis_enterprise_services.planning.naming.configured_name_rules import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.site_placement import SitePlacement
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming

CONTEXT: NamingContext = NamingContext(
    active_active=False,
    sites=[SitePlacement(network="net-a", site="ny", environment="PROD", cluster="generic")],
)


@pytest.fixture
def validator() -> UserNamesValidator:
    rules: RedisNameRulesSettings = load_settings().naming.redis
    return UserNamesValidator(
        user_name_validator=NameValidator(rules=configured_name_rules(settings=rules.user)),
        acl_and_role_name_validator=NameValidator(rules=configured_name_rules(settings=rules.acl_and_role)),
        resource_naming=UserResourceNaming(
            settings=UserResourcesSettings(
                acl_name_template="{database}-{user}-acl",
                role_name_template="{database}-{user}-role",
                role_management="db_viewer",
            )
        ),
    )


def spec_with_user(*, name: str) -> DatabaseSpec:
    return DatabaseSpec(
        database=NewDatabase(name="orders", memory_size=1),
        users=[DatabaseUserSpec(name=name, password="p", acl_rule="+@all")],
    )


@pytest.mark.parametrize(argnames="name", argvalues=["app", "app_1", "a.b", "a@b", "a b"])
def test_names_redis_accepts_for_the_user_its_acl_and_role_pass(
    validator: UserNamesValidator, name: str
) -> None:
    validator.ensure_valid(spec=spec_with_user(name=name), context=CONTEXT)


@pytest.mark.parametrize(
    argnames="name",
    argvalues=[
        pytest.param('a"b', id="refused by Redis for a user"),
        pytest.param("a/b", id="fine for a user, refused by Redis in the ACL and role names"),
        pytest.param("שם", id="not ASCII"),
        pytest.param("a" * 250, id="derived names longer than 255"),
    ],
)
def test_names_redis_refuses_are_refused_at_once(validator: UserNamesValidator, name: str) -> None:
    with pytest.raises(expected_exception=InvalidNameError):
        validator.ensure_valid(spec=spec_with_user(name=name), context=CONTEXT)
