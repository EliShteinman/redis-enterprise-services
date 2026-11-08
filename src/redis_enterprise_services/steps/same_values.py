import json

from pydantic import JsonValue


def same_values(
    *, current: dict[str, JsonValue], expected: dict[str, JsonValue], unordered_fields: frozenset[str]
) -> bool:
    return current.keys() == expected.keys() and all(
        same_field(current=current[name], expected=expected[name], ignore_order=name in unordered_fields)
        for name in expected
    )


def same_field(*, current: JsonValue, expected: JsonValue, ignore_order: bool) -> bool:
    if ignore_order and isinstance(current, list) and isinstance(expected, list):
        return sorted(map(canonical_json, current)) == sorted(map(canonical_json, expected))
    return canonical_json(current) == canonical_json(expected)


def canonical_json(value: JsonValue) -> str:
    return json.dumps(whole_numbers_as_int(value=value), sort_keys=True)


def whole_numbers_as_int(*, value: JsonValue) -> JsonValue:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [whole_numbers_as_int(value=item) for item in value]
    if isinstance(value, dict):
        return {key: whole_numbers_as_int(value=item) for key, item in value.items()}
    return value
