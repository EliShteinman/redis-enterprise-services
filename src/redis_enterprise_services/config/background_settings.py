from pydantic import BaseModel, PositiveInt


class BackgroundSettings(BaseModel):
    max_workers: PositiveInt
