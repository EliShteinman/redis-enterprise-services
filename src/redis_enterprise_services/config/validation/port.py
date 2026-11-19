from typing import Annotated

from pydantic import Field

type Port = Annotated[int, Field(gt=0, le=65535)]
