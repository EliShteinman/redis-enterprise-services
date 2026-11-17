from typing import Annotated

from pydantic import JsonValue, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from redis_enterprise_services.databases.new_database import (
    SHARD_KEY_REGEX_FIELD,
    SHARDING_FIELD,
    SHARDS_COUNT_FIELD,
    DatabaseOptions,
    holds_sharding_only_values,
)
from redis_enterprise_services.exceptions.configuration import ConfigurationError


def typed_level_values(*, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    typed: dict[str, JsonValue] = {
        name: typed_value(name=name, value=value) for name, value in values.items() if value is not None
    }
    reject_sharding_off_with_sharding_values(values=typed)
    return typed


def typed_value(*, name: str, value: JsonValue) -> JsonValue:
    field: FieldInfo | None = DatabaseOptions.model_fields.get(name)
    if field is None:
        raise ConfigurationError(message=f"{name} is not a database option")
    adapter: TypeAdapter[object] = TypeAdapter[object](
        Annotated[field.annotation, field]  # pyright: ignore[reportArgumentType, reportInvalidTypeForm, reportUnknownMemberType]
    )
    try:
        return adapter.dump_python(adapter.validate_python(value), mode="json")
    except ValidationError as error:
        raise ConfigurationError(message=f"database value {name} is not valid: {error}") from error


def reject_sharding_off_with_sharding_values(*, values: dict[str, JsonValue]) -> None:
    if values.get(SHARDING_FIELD) is False and holds_sharding_only_values(
        shard_key_regex=values.get(SHARD_KEY_REGEX_FIELD), shards_count=values.get(SHARDS_COUNT_FIELD)
    ):
        raise ConfigurationError(
            message="shard_key_regex and shards_count above 1 are not set together with sharding false "
            "on one level"
        )
