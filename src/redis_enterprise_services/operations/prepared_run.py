from collections.abc import Callable

from pydantic import BaseModel


class PreparedRun(BaseModel):
    name: str
    task: Callable[[], object]
