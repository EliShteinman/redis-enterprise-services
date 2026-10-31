from typing import Protocol

from redis_enterprise_services.planning.naming.name_violation import NameViolation
from redis_enterprise_services.planning.naming.naming_context import NamingContext


class NameRule(Protocol):
    def violation(self, *, name: str, context: NamingContext) -> NameViolation | None: ...
