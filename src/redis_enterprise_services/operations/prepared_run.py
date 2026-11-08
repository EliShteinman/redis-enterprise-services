from collections.abc import Callable

from pydantic import BaseModel


class PreparedRun(BaseModel):
    task_name: str
    task: Callable[[], object]
