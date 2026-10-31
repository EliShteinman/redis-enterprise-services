import logging

from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.planning.naming.name_rule import NameRule
from redis_enterprise_services.planning.naming.naming_context import NamingContext

logger: logging.Logger = logging.getLogger(name=__name__)


class NameValidator:
    def __init__(self, *, rules: list[NameRule]) -> None:
        self._rules: list[NameRule] = rules

    def violations(self, *, name: str, context: NamingContext) -> list[str]:
        found: list[str | None] = [rule.violation(name=name, context=context) for rule in self._rules]
        return [violation for violation in found if violation is not None]

    def ensure_valid(self, *, name: str, context: NamingContext) -> None:
        violations: list[str] = self.violations(name=name, context=context)
        if violations:
            message: str = "; ".join(violations)
            logger.warning(msg=message)
            raise InvalidNameError(message=message)
