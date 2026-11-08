from fastapi import APIRouter
from pydantic import BaseModel

router: APIRouter = APIRouter()


class LivenessStatus(BaseModel):
    status: str


@router.get(path="/health")
def liveness() -> LivenessStatus:
    return LivenessStatus(status="ok")
