import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

ServiceStatus = Literal["ativo", "inativo"]


class ServiceBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    category: str = Field(min_length=2, max_length=60)
    duration_min: int = Field(ge=5, le=600)
    price_cents: int = Field(ge=0, le=100_000_000)
    status: ServiceStatus = "ativo"
    operational_notes: str = Field(default="", max_length=1000)


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    duration_min: int | None = Field(default=None, ge=5, le=600)
    price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    status: ServiceStatus | None = None
    operational_notes: str | None = Field(default=None, max_length=1000)


class Service(ServiceBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_demo: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ServiceListOut(BaseModel):
    items: list[Service]
    total: int
