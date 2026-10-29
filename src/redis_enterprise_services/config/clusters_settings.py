from typing import Literal

from pydantic import BaseModel

type Environment = Literal["DEV", "PROD", "TEST"]
type ClusterType = Literal["generic", "dedicated"]


class ClusterEntry(BaseModel):
    name: str
    network: str
    environment: Environment
    site: str
    type: ClusterType
    api_url: str
