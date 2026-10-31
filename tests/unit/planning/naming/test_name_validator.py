import pytest

from redis_enterprise_services.config.naming_settings import NameRulesSettings
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.planning.naming.name_rule import NameRule
from redis_enterprise_services.planning.naming.name_rules_factory import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.site_target import ClusterChoice, SiteTarget

RULES: list[NameRule] = configured_name_rules(
    settings=NameRulesSettings(pattern="^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$", max_length=10)
)
CONTEXT: NamingContext = NamingContext(
    active_active=False,
    sites=[SiteTarget(network="net-a", site="ny", environment="PROD", cluster=ClusterChoice(type="generic"))],
)


class EndsWithSiteRule:
    def violation(self, *, name: str, context: NamingContext) -> str | None:
        site: str = context.sites[0].site
        return None if name.endswith(site) else f"{name} does not end with {site}"


@pytest.mark.parametrize(
    argnames=("name", "count"),
    argvalues=[
        pytest.param("orders-1", 0, id="valid"),
        pytest.param("orders-123", 0, id="exactly the max length"),
        pytest.param("orders_1", 1, id="outside the pattern"),
        pytest.param("orders-12345", 1, id="too long"),
        pytest.param("orders_12345", 2, id="every broken rule is reported"),
    ],
)
def test_the_configured_rules_report_each_violation(name: str, count: int) -> None:
    assert len(NameValidator(rules=RULES).violations(name=name, context=CONTEXT)) == count


def test_an_added_rule_judges_the_name_by_its_context() -> None:
    validator: NameValidator = NameValidator(rules=[*RULES, EndsWithSiteRule()])

    assert validator.violations(name="orders-la", context=CONTEXT) == ["orders-la does not end with ny"]


def test_an_invalid_name_is_refused() -> None:
    with pytest.raises(expected_exception=InvalidNameError):
        NameValidator(rules=RULES).ensure_valid(name="orders_1", context=CONTEXT)
