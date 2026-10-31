from redis_enterprise_services.planning.naming.naming_context import NamingContext


class MaxLengthRule:
    def __init__(self, *, max_length: int) -> None:
        self._max_length: int = max_length

    def violation(self, *, name: str, context: NamingContext) -> str | None:
        if len(name) <= self._max_length:
            return None
        return f"{name} is longer than {self._max_length} characters"
