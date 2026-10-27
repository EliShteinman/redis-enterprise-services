from pydantic import BaseModel


class UserSettings(BaseModel):
    collection_path: str
    path: str
