from pydantic import JsonValue, ValidationError


def string_field(*, body: JsonValue, name: str) -> str | None:
    value: JsonValue = body.get(name) if isinstance(body, dict) else None
    return value if isinstance(value, str) else None


def failed_fields(*, error: ValidationError) -> list[str]:
    return [".".join(str(part) for part in detail["loc"]) for detail in error.errors(include_input=False)]
