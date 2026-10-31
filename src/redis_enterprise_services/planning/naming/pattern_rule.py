import re

from redis_enterprise_services.planning.naming.name_violation import NameViolation
from redis_enterprise_services.planning.naming.naming_context import NamingContext

RULE: str = "pattern"


class PatternRule:
    def __init__(self, *, pattern: re.Pattern[str]) -> None:
        self._pattern: re.Pattern[str] = pattern

    def violation(self, *, name: str, context: NamingContext) -> NameViolation | None:
        if self._pattern.fullmatch(name):
            return None
        return NameViolation(rule=RULE, message=f"{name} does not match {self._pattern.pattern}")
