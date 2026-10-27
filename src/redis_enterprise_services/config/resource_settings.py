from pydantic import BaseModel


class ResourceSettings(BaseModel):
    collection_path: str
    path: str
