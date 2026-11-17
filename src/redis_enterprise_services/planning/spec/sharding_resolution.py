from pydantic import JsonValue

from redis_enterprise_services.databases.new_database import (
    SHARD_KEY_REGEX_FIELD,
    SHARDING_FIELD,
    SHARDS_COUNT_FIELD,
    SINGLE_SHARD,
    holds_sharding_only_values,
)
from redis_enterprise_services.exceptions.configuration import ConfigurationError


def layered_database_values(*, layers: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = {}
    for layer in layers:
        below: dict[str, JsonValue] = (
            values if layer.get(SHARDING_FIELD) is not False else without_sharding_only_values(values=values)
        )
        values = {**below, **layer}
    return values


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
    if sharding is None and asks_for_sharding(values=values):
        sharding = True
    if sharding is True:
        return {**sharding_values, **values, SHARDING_FIELD: True}
    if sharding is False:
        return {SHARDS_COUNT_FIELD: SINGLE_SHARD, **values}
    return values


def asks_for_sharding(*, values: dict[str, JsonValue]) -> bool:
    return holds_sharding_only_values(
        shard_key_regex=values.get(SHARD_KEY_REGEX_FIELD), shards_count=values.get(SHARDS_COUNT_FIELD)
    )


def reject_sharding_without_its_rules(*, values: dict[str, JsonValue]) -> None:
    if values.get(SHARDING_FIELD) is True and not values.get(SHARD_KEY_REGEX_FIELD):
        raise ConfigurationError(
            message="a sharded database needs shard_key_regex, and database_defaults.sharding_values has none"
        )
