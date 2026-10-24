from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException

from lib.authz import ROLE_LABELS, Principal, TenantRepo, audit, require
from lib.db import db
from lib.demo import reset_demo
from lib.funnel import STAGE_CODES
from models.auth import ClinicOut, MemberOut
from models.clinic import ClinicUpdate, StagesUpdate
from models.common import OkOut

router = APIRouter(tags=["clinic"])


async def _clinic(principal: Principal) -> ClinicOut:
    doc = await db.clinics.find_one({"id": principal.clinic_id}, {"_id": 0})
    return ClinicOut(**doc)


@router.patch("/clinic", response_model=ClinicOut)
async def update_clinic(body: ClinicUpdate, principal: Principal = Depends(require("settings:write"))):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "timezone" in changes:
        try:
            ZoneInfo(changes["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(status_code=422, detail="Fuso horário inválido")
    if changes:
        # Changing currency never rewrites stored amounts (no financial records exist in Phase 1).
        await db.clinics.update_one({"id": principal.clinic_id}, {"$set": changes})
        await audit(principal.clinic_id, principal.user_id, "clinic_settings_updated", "clinic",
                    principal.clinic_id, {"fields": sorted(changes)})
    return await _clinic(principal)


@router.patch("/clinic/stages", response_model=ClinicOut)
async def update_stages(body: StagesUpdate, principal: Principal = Depends(require("stages:configure"))):
    codes = [s.code for s in body.stages]
    if sorted(codes) != sorted(STAGE_CODES):
        raise HTTPException(status_code=422, detail="Todas as etapas devem ser informadas uma única vez; códigos não podem ser alterados")
    current = {s["code"] for s in principal.clinic["stages"]}
    if current != set(codes):
        raise HTTPException(status_code=422, detail="Códigos de etapa inválidos")
    stages = [s.model_dump() for s in body.stages]
    await db.clinics.update_one({"id": principal.clinic_id}, {"$set": {"stages": stages, "show_lost": body.show_lost}})
    await audit(principal.clinic_id, principal.user_id, "stages_configured", "clinic", principal.clinic_id)
    return await _clinic(principal)


@router.get("/users", response_model=list[MemberOut])
async def list_users(principal: Principal = Depends(require("users:read"))):
    repo = TenantRepo(principal)
    users = await repo.find("users", {"active": True}, sort=[("name", 1)])
    return [MemberOut(id=u["id"], name=u["name"], role=u["role"], role_label=ROLE_LABELS[u["role"]]) for u in users]


@router.post("/demo/reset", response_model=OkOut)
async def demo_reset(principal: Principal = Depends(require("demo:reset"))):
    if not principal.clinic.get("is_demo"):
        raise HTTPException(status_code=400, detail="A restauração está disponível apenas na clínica de demonstração")
    await reset_demo(principal.clinic_id)
    await audit(principal.clinic_id, principal.user_id, "demo_reset", "clinic", principal.clinic_id)
    return OkOut(message="Dados de demonstração restaurados")
