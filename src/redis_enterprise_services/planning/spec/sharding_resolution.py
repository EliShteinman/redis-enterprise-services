from pydantic import JsonValue

from redis_enterprise_services.databases.new_database import (
    SHARD_KEY_REGEX_FIELD,
    SHARDING_FIELD,
    SHARDS_COUNT_FIELD,
    SINGLE_SHARD,
    holds_sharding_only_values,
)


def layered_database_values(*, layers: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = {}
    for layer in layers:
        values = {**fitting_below(values=values, layer=layer), **layer}
    return values


def fitting_below(*, values: dict[str, JsonValue], layer: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if layer.get(SHARDING_FIELD) is False:
        return without_sharding_only_values(values=values)
    if SHARDING_FIELD not in layer and asks_for_sharding(values=layer):
        return without_sharding_off(values=values)
    return values


def without_sharding_off(*, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {name: value for name, value in values.items() if not (name == SHARDING_FIELD and value is False)}


def without_sharding_only_values(*, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        name: value for name, value in values.items() if not is_sharding_only_value(name=name, value=value)
    }


def is_sharding_only_value(*, name: str, value: JsonValue) -> bool:
    if name == SHARD_KEY_REGEX_FIELD:
        return holds_sharding_only_values(shard_key_regex=value, shards_count=None)
    if name == SHARDS_COUNT_FIELD:
        return holds_sharding_only_values(shard_key_regex=None, shards_count=value)
    return False


def with_sharding_completed(
    *, values: dict[str, JsonValue], sharding_values: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    sharding: JsonValue = values.get(SHARDING_FIELD)
    if sharding is None:
        sharding = asks_for_sharding(values=values)
    if sharding is True:
        return {**sharding_values, **values, SHARDING_FIELD: True}
    return {SHARDS_COUNT_FIELD: SINGLE_SHARD, **values, SHARDING_FIELD: False}


def asks_for_sharding(*, values: dict[str, JsonValue]) -> bool:
    return holds_sharding_only_values(
        shard_key_regex=values.get(SHARD_KEY_REGEX_FIELD), shards_count=values.get(SHARDS_COUNT_FIELD)
    )
