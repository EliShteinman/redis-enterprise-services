from typing import ClassVar

from pydantic import BaseModel, ConfigDict, SecretStr


class ClusterCredentials(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    username: str
    password: SecretStr
