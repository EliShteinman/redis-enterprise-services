from pydantic import BaseModel

from redis_enterprise_services.config.port import Port


class ServerSettings(BaseModel):
    host: str
    port: Port
