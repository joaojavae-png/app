from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from lib.authz import Principal, TenantRepo, require
from lib.indicators import REGISTRY, compute_values, validate_target
from lib.periods import PRESET_LABELS, resolve_period
from models.indicators import IndicatorDefinition, IndicatorValue, IndicatorValuesOut

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("/registry", response_model=list[IndicatorDefinition])
async def registry(principal: Principal = Depends(require("indicators:read"))):
    return [IndicatorDefinition(**d) for d in REGISTRY]


@router.get("/values", response_model=IndicatorValuesOut)
async def values(
    period: str = "all", start: str | None = None, end: str | None = None,
    target_stage: str = "consulta_agendada", window_days: int = Query(30, ge=1, le=365),
    principal: Principal = Depends(require("dashboard:read")),
):
    if not validate_target(target_stage):
        raise HTTPException(status_code=422, detail="Etapa-alvo inválida")
    clinic = principal.clinic
    s, e = resolve_period(period, start, end, clinic["timezone"])
    vals = await compute_values(TenantRepo(principal), clinic, s, e, target_stage, window_days)
    return IndicatorValuesOut(
        period=period, period_label=PRESET_LABELS[period], period_start=s, period_end=e,
        previous_start=(s - (e - s)) if s and e else None, previous_end=s,
        target_stage=target_stage, window_days=window_days, is_demo=bool(clinic.get("is_demo")),
        computed_at=datetime.now(timezone.utc), timezone=clinic["timezone"],
        values=[IndicatorValue(**v) for v in vals],
    )
