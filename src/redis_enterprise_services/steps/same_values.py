import json

from pydantic import JsonValue


def same_values(*, stored: dict[str, JsonValue], wanted: dict[str, JsonValue]) -> bool:
    return normalized(value=stored) == normalized(value=wanted)


def normalized(*, value: JsonValue) -> JsonValue:
    if isinstance(value, list):
        items: list[JsonValue] = [normalized(value=item) for item in value]
        return sorted(items, key=canonical)
    if isinstance(value, dict):
        return {key: normalized(value=item) for key, item in value.items()}
    return value


def canonical(value: JsonValue) -> str:
    return json.dumps(value, sort_keys=True)
