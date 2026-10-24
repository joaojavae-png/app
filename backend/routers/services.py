import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from lib.authz import Principal, TenantRepo, audit, require
from models.services import Service, ServiceCreate, ServiceListOut, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


async def _name_taken(repo: TenantRepo, name: str, exclude_id: str | None = None) -> bool:
    flt: dict = {"name": {"$regex": f"^{re.escape(name.strip())}$", "$options": "i"}}
    if exclude_id:
        flt["id"] = {"$ne": exclude_id}
    return await repo.count("services", flt) > 0


@router.get("", response_model=ServiceListOut)
async def list_services(status: Literal["ativo", "inativo", "todos"] = "todos", q: str = "",
                        principal: Principal = Depends(require("services:read"))):
    repo = TenantRepo(principal)
    flt: dict = {}
    if status != "todos":
        flt["status"] = status
    if q.strip():
        flt["$or"] = [{"name": {"$regex": re.escape(q.strip()), "$options": "i"}},
                      {"category": {"$regex": re.escape(q.strip()), "$options": "i"}}]
    items = await repo.find("services", flt, sort=[("name", 1)])
    return ServiceListOut(items=[Service(**s) for s in items], total=len(items))


@router.get("/{id}", response_model=Service)
async def get_service(id: str, principal: Principal = Depends(require("services:read"))):
    doc = await TenantRepo(principal).find_one("services", {"id": id})
    if not doc:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return Service(**doc)


@router.post("", response_model=Service, status_code=201)
async def create_service(body: ServiceCreate, principal: Principal = Depends(require("services:write"))):
    repo = TenantRepo(principal)
    if await _name_taken(repo, body.name):
        raise HTTPException(status_code=409, detail="Já existe um serviço com este nome")
    svc = Service(**body.model_dump(), is_demo=False)
    await repo.insert("services", svc.model_dump())
    await audit(principal.clinic_id, principal.user_id, "service_created", "service", svc.id)
    return svc


@router.patch("/{id}", response_model=Service)
async def update_service(id: str, body: ServiceUpdate, principal: Principal = Depends(require("services:write"))):
    repo = TenantRepo(principal)
    doc = await repo.find_one("services", {"id": id})
    if not doc:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes and await _name_taken(repo, changes["name"], exclude_id=id):
        raise HTTPException(status_code=409, detail="Já existe um serviço com este nome")
    if changes:
        changes["updated_at"] = datetime.now(timezone.utc)
        await repo.update_one("services", {"id": id}, {"$set": changes})
        await audit(principal.clinic_id, principal.user_id, "service_updated", "service", id, {"fields": sorted(changes)})
    return Service(**(await repo.find_one("services", {"id": id})))
