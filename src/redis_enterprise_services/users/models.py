from pydantic import BaseModel


class NewUser(BaseModel):
    name: str
    password: str
    role_uids: list[int]
