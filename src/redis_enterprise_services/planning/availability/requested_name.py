from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

type NameKind = Literal["database", "acl", "role", "user"]


class RequestedName(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: NameKind
    name: str
