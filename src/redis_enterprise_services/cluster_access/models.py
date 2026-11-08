from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, SecretStr

type HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class ClusterCredentials(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    username: str
    password: SecretStr
