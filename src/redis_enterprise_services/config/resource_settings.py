from pydantic import BaseModel, Field


class ResourceSettings(BaseModel):
    collection_path: str
    path: str
    list_fields: list[str] = Field(default_factory=list)


class RoleSettings(ResourceSettings):
    database_resource_type: str
