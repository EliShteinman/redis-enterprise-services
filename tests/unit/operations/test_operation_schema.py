from pydantic import JsonValue

from redis_enterprise_services.operations.operation import Operation


def test_the_operation_schema_always_has_its_status_and_database() -> None:
    schema: dict[str, JsonValue] = Operation.model_json_schema(mode="serialization")

    assert schema["required"] == ["trace_id", "status", "database"]
