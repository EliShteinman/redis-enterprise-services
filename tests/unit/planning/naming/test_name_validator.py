import pytest

from redis_enterprise_services.config.naming_settings import NameRulesSettings
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.planning.naming.configured_name_rules import configured_name_rules
from redis_enterprise_services.planning.naming.name_rule import NameRule
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.name_violation import NameViolation
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.site_placement import ClusterChoice, SitePlacement

RULES: list[NameRule] = configured_name_rules(
    settings=NameRulesSettings.model_validate(
        obj={"pattern": "^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$", "max_length": 10}
    )
)
CONTEXT: NamingContext = NamingContext(
    active_active=False,
    sites=[
        SitePlacement(network="net-a", site="ny", environment="PROD", cluster=ClusterChoice(type="generic"))
    ],
)


class EndsWithSiteRule:
    def violation(self, *, name: str, context: NamingContext) -> NameViolation | None:
        site: str = context.sites[0].site
        return None if name.endswith(site) else NameViolation(rule="site_suffix", message=f"ends with {site}")


@pytest.mark.parametrize(
    argnames=("name", "rules"),
    argvalues=[
        pytest.param("orders-1", [], id="valid"),
        pytest.param("orders-123", [], id="exactly the max length"),
        pytest.param("orders_1", ["pattern"], id="outside the pattern"),
        pytest.param("orders-12345", ["max_length"], id="too long"),
        pytest.param("orders_12345", ["pattern", "max_length"], id="every broken rule is reported"),
    ],
)
def test_the_configured_rules_report_each_violation(name: str, rules: list[str]) -> None:
    assert [
        violation.rule for violation in NameValidator(rules=RULES).violations(name=name, context=CONTEXT)
    ] == rules


def test_an_added_rule_judges_the_name_by_its_context() -> None:
    validator: NameValidator = NameValidator(rules=[*RULES, EndsWithSiteRule()])

    assert [violation.rule for violation in validator.violations(name="orders-la", context=CONTEXT)] == [
        "site_suffix"
    ]


def test_an_invalid_name_is_refused() -> None:
    with pytest.raises(expected_exception=InvalidNameError):
        NameValidator(rules=RULES).ensure_valid(name="orders_1", context=CONTEXT)
