from pydantic import BaseModel, JsonValue


class DatabaseFields(BaseModel):
    values: dict[str, JsonValue]
    cluster_state_id: int
