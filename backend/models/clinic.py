from typing import Literal

from pydantic import BaseModel, Field

from models.common import StageCode


class ClinicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    currency: Literal["BRL", "USD", "EUR"] | None = None
    timezone: str | None = Field(default=None, max_length=64)


class StageConfigIn(BaseModel):
    code: StageCode
    label: str = Field(min_length=2, max_length=40)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class StagesUpdate(BaseModel):
    stages: list[StageConfigIn]
    show_lost: bool = True
