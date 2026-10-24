from datetime import datetime

from pydantic import BaseModel


class IndicatorDefinition(BaseModel):
    id: str
    code: str
    name: str
    description: str
    objective: str
    kind: str  # snapshot | fluxo | coorte
    formula: str
    numerator: str | None
    denominator: str | None
    unit: str
    source: str
    filters: list[str]
    inclusion: str
    exclusion: str
    frequency: str
    attribution: str
    limitations: str
    available: bool
    depends_on: str | None = None
    module: str


class BreakdownItem(BaseModel):
    key: str
    label: str
    value: float
    color: str | None = None


class IndicatorValue(BaseModel):
    id: str
    status: str  # ok | sem_dados | indisponivel
    value: float | None = None
    previous_value: float | None = None
    numerator: float | None = None
    denominator: float | None = None
    unit: str
    breakdown: list[BreakdownItem] = []
    notes: list[str] = []


class IndicatorValuesOut(BaseModel):
    period: str
    period_label: str
    period_start: datetime | None
    period_end: datetime | None
    previous_start: datetime | None
    previous_end: datetime | None
    target_stage: str
    window_days: int
    is_demo: bool
    computed_at: datetime
    timezone: str
    values: list[IndicatorValue]
