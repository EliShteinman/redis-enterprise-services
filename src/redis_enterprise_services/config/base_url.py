from typing import Annotated

from pydantic import Field

type BaseUrl = Annotated[str, Field(pattern=r"^https?://[^/\s]+(/\S*[^/\s])?$")]
