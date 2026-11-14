from pydantic import JsonValue

from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError


def string_field(*, body: JsonValue, name: str) -> str | None:
    value: JsonValue = body.get(name) if isinstance(body, dict) else None
    return value if isinstance(value, str) else None


def required_string_field(*, body: JsonValue, name: str, missing_message: str) -> str:
    value: str | None = string_field(body=body, name=name)
    if value is None:
        raise UnreadableClusterResponseError(message=missing_message)
    return value
