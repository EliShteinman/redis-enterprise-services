from pydantic import JsonValue


def string_field(*, body: JsonValue, name: str) -> str | None:
    value: JsonValue = body.get(name) if isinstance(body, dict) else None
    return value if isinstance(value, str) else None
