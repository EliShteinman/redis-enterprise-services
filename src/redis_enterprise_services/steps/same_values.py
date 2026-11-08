import json

from pydantic import JsonValue


def same_values(
    *, stored: dict[str, JsonValue], wanted: dict[str, JsonValue], unordered_fields: frozenset[str]
) -> bool:
    return stored.keys() == wanted.keys() and all(
        same_field(stored=stored[name], wanted=wanted[name], unordered=name in unordered_fields)
        for name in wanted
    )


def same_field(*, stored: JsonValue, wanted: JsonValue, unordered: bool) -> bool:
    if unordered and isinstance(stored, list) and isinstance(wanted, list):
        return sorted(map(canonical, stored)) == sorted(map(canonical, wanted))
    return canonical(stored) == canonical(wanted)


def canonical(value: JsonValue) -> str:
    return json.dumps(whole_numbers_as_int(value=value), sort_keys=True)


def whole_numbers_as_int(*, value: JsonValue) -> JsonValue:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [whole_numbers_as_int(value=item) for item in value]
    if isinstance(value, dict):
        return {key: whole_numbers_as_int(value=item) for key, item in value.items()}
    return value
