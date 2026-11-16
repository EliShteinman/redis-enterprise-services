from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field


class LivenessStatus(BaseModel):
    status: Literal["ok"] = Field(description="ok while the process answers requests.", examples=["ok"])


def liveness() -> LivenessStatus:
    return LivenessStatus(status="ok")


def liveness_router(*, path: str) -> APIRouter:
    router: APIRouter = APIRouter()
    router.get(path=path)(liveness)
    return router
