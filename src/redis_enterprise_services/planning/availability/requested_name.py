from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.planning.name_kind import NameKind


class RequestedName(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: NameKind
    name: str
