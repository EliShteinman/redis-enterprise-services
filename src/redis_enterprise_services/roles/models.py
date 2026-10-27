from pydantic import BaseModel


class NewRole(BaseModel):
    name: str
    management: str
    database_uids: list[int]
