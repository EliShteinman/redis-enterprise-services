from functools import cache
from typing import Annotated

from pydantic import JsonValue, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from redis_enterprise_services.databases.new_database import (
    SHARD_KEY_REGEX_FIELD,
    SHARDING_FIELD,
    SHARDING_OFF_CONTRADICTION,
    SHARDS_COUNT_FIELD,
    DatabaseOptions,
    contradicts_sharding_off,
)
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.spec.validation_issues import issues_text


def typed_level_values(*, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    typed: dict[str, JsonValue] = {
        name: typed_value(name=name, value=value) for name, value in values.items() if value is not None
    }
    reject_sharding_off_with_sharding_values(values=typed)
    return typed


def typed_value(*, name: str, value: JsonValue) -> JsonValue:
    adapter: TypeAdapter[object] = option_adapter(name=name)
    try:
        return adapter.dump_python(adapter.validate_python(value), mode="json")
    except ValidationError as error:
        raise ConfigurationError(
            message=f"database value {name} is not valid: {issues_text(error=error)}"
        ) from error


@cache
def option_adapter(*, name: str) -> TypeAdapter[object]:
    field: FieldInfo | None = DatabaseOptions.model_fields.get(name)
    if field is None:
        raise ConfigurationError(message=f"{name} is not a database option")
    return TypeAdapter[object](
        Annotated[field.annotation, field]  # pyright: ignore[reportArgumentType, reportInvalidTypeForm, reportUnknownMemberType]
    )


def reject_sharding_off_with_sharding_values(*, values: dict[str, JsonValue]) -> None:
    if contradicts_sharding_off(
        sharding=values.get(SHARDING_FIELD),
        shard_key_regex=values.get(SHARD_KEY_REGEX_FIELD),
        shards_count=values.get(SHARDS_COUNT_FIELD),
    ):
        raise ConfigurationError(message=f"{SHARDING_OFF_CONTRADICTION} on one level")
