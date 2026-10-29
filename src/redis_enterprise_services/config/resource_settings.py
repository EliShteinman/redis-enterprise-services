from pydantic import BaseModel


class ResourceSettings(BaseModel):
    collection_path: str
    path: str
    list_fields: list[str]


class RoleSettings(ResourceSettings):
    database_resource_type: str
