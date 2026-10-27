from pydantic import BaseModel, SecretStr, field_serializer


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


class UserCreationBody(BaseModel):
    name: str
    password: SecretStr
    role_uids: list[int]

    @field_serializer("password")
    def reveal_password(self, password: SecretStr) -> str:
        return password.get_secret_value()
