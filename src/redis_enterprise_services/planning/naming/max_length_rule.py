from redis_enterprise_services.planning.naming.name_rule import NameRule
from redis_enterprise_services.planning.naming.name_violation import NameViolation
from redis_enterprise_services.planning.naming.naming_context import NamingContext

MAX_LENGTH_RULE_ID: str = "max_length"


class MaxLengthRule(NameRule):
    def __init__(self, *, max_length: int) -> None:
        self._max_length: int = max_length

    def violation(self, *, name: str, context: NamingContext) -> NameViolation | None:
        if len(name) <= self._max_length:
            return None
        return NameViolation(
            rule_id=MAX_LENGTH_RULE_ID, message=f"{name} is longer than {self._max_length} characters"
        )
