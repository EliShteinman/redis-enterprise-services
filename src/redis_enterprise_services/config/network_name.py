from typing import Annotated

from pydantic import StringConstraints

type NetworkName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(_[a-z0-9]+)*$")]
