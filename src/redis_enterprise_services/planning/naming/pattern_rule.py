import re

from redis_enterprise_services.planning.naming.naming_context import NamingContext


class PatternRule:
    def __init__(self, *, pattern: str) -> None:
        self._pattern: re.Pattern[str] = re.compile(pattern)

    def violation(self, *, name: str, context: NamingContext) -> str | None:
        if self._pattern.fullmatch(name):
            return None
        return f"{name} does not match {self._pattern.pattern}"
