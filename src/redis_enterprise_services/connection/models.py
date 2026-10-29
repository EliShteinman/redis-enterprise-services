from typing import Literal

from pydantic import BaseModel, SecretStr

type HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class ClusterCredentials(BaseModel):
    username: str
    password: SecretStr
