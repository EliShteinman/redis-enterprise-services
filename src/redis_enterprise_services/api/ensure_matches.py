import re

from redis_enterprise_services.api.field_validation_error import field_validation_error


def ensure_matches(*, value: str, pattern: re.Pattern[str], location: tuple[str, str], message: str) -> None:
    if pattern.fullmatch(value) is None:
        raise field_validation_error(location=location, message=message)
