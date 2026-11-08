from redis_enterprise_services.config.naming_settings import NameRulesSettings
from redis_enterprise_services.planning.naming.max_length_rule import MaxLengthRule
from redis_enterprise_services.planning.naming.name_rule import NameRule
from redis_enterprise_services.planning.naming.pattern_rule import PatternRule


def configured_name_rules(*, settings: NameRulesSettings) -> list[NameRule]:
    return [PatternRule(pattern=settings.pattern), MaxLengthRule(max_length=settings.max_length)]
