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
    return json.dumps(value, sort_keys=True)
