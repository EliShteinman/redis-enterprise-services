from pydantic import BaseModel, SecretStr


class NewUser(BaseModel):
    name: str
    password: SecretStr
    role_uids: list[int]


class User(BaseModel):
    uid: int
    name: str
    role_uids: list[int]


class CreatedUser(BaseModel):
    user: User
    action_uid: str | None
