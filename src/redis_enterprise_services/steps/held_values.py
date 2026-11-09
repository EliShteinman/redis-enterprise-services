from enum import StrEnum

from pydantic import JsonValue

from redis_enterprise_services.steps.same_values import same_values


class HeldValues(StrEnum):
    NEW = "new"
    OLD = "old"
    BOTH = "both"
    NEITHER = "neither"


def held_values(
    *,
    current: dict[str, JsonValue],
    new_values: dict[str, JsonValue],
    old_values: dict[str, JsonValue],
    order_insensitive_fields: frozenset[str],
) -> HeldValues:
    holds_new: bool = same_values(
        current=current, expected=new_values, order_insensitive_fields=order_insensitive_fields
    )
    holds_old: bool = same_values(
        current=current, expected=old_values, order_insensitive_fields=order_insensitive_fields
    )
    if holds_new and holds_old:
        return HeldValues.BOTH
    if holds_new:
        return HeldValues.NEW
    if holds_old:
        return HeldValues.OLD
    return HeldValues.NEITHER
