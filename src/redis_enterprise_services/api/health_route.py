from fastapi import APIRouter
from pydantic import BaseModel

router: APIRouter = APIRouter()


class HealthStatus(BaseModel):
    status: str


@router.get(path="/health")
def health() -> HealthStatus:
    return HealthStatus(status="ok")
