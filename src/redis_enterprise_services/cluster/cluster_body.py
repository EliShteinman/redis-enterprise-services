from pydantic import JsonValue, TypeAdapter, ValidationError

from redis_enterprise_services.cluster.invalid_field_paths import invalid_field_paths
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError


def parse_cluster_body[T](*, body: JsonValue, adapter: TypeAdapter[T], message_prefix: str) -> T:
    try:
        return adapter.validate_python(body)
    except ValidationError as error:
        raise UnreadableClusterResponseError(
            message=f"{message_prefix} {invalid_field_paths(error=error)}"
        ) from error
