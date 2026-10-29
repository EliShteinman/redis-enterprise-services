from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue


class DatabaseFields(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(hide_input_in_errors=True)

    values: dict[str, JsonValue]
    cluster_state_id: int
