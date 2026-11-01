from pydantic import BaseModel, PositiveInt


class ServerSettings(BaseModel):
    host: str
    port: PositiveInt
