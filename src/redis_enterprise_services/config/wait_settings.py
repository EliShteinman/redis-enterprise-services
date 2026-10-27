from pydantic import BaseModel, PositiveFloat


class WaitSettings(BaseModel):
    interval_seconds: PositiveFloat
    timeout_seconds: PositiveFloat
