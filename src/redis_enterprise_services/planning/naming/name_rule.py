from typing import Protocol

from redis_enterprise_services.planning.naming.naming_context import NamingContext


class NameRule(Protocol):
    def violation(self, *, name: str, context: NamingContext) -> str | None: ...
