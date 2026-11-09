from pydantic import ConfigDict, JsonValue, TypeAdapter

from redis_enterprise_services.cluster.cluster_body import parse_cluster_body

OBJECT_ADAPTER: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(
    type=dict[str, JsonValue], config=ConfigDict(hide_input_in_errors=True)
)


def object_body(*, body: JsonValue, message_prefix: str) -> dict[str, JsonValue]:
    return parse_cluster_body(body=body, adapter=OBJECT_ADAPTER, message_prefix=message_prefix)


def without_fields(*, fields: dict[str, JsonValue], names: frozenset[str]) -> dict[str, JsonValue]:
    return {name: value for name, value in fields.items() if name not in names}
