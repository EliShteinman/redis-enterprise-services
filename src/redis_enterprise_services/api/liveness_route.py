from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router: APIRouter = APIRouter()


class LivenessStatus(BaseModel):
    status: Literal["ok"] = Field(description="ok while the process answers requests.", examples=["ok"])


@router.get(path="/health")
def liveness() -> LivenessStatus:
    return LivenessStatus(status="ok")
