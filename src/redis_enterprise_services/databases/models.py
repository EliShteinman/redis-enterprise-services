from pydantic import BaseModel, ConfigDict, JsonValue


class DatabaseFields(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    values: dict[str, JsonValue]
    cluster_state_id: int
