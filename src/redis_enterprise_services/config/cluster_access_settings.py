from pydantic import BaseModel, Field, SecretStr


class ClusterAccessSettings(BaseModel):
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
