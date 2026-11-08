from collections.abc import Callable

from pydantic import BaseModel


class PreparedRun(BaseModel):
    description: str
    task: Callable[[], object]
