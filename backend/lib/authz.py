"""Authorization: one permission model, one principal dependency, one tenant-scoped repository.

Model: RBAC per clinic. Admin has every permission of its own clinic. Gestor gets an operational
base set plus ONLY the high-impact permissions explicitly granted on the user record. Every
query goes through TenantRepo, which forces `clinic_id` from the server-side principal.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request

from lib.db import db
from lib.security import COOKIE_NAME, decode_token

ROLES = ["admin", "gestor", "atendente", "profissional", "financeiro", "estoque"]

ROLE_LABELS = {
    "admin": "Admin",
    "gestor": "Gestor",
    "atendente": "Atendente",
    "profissional": "Profissional",
    "financeiro": "Financeiro",
    "estoque": "Estoque",
}

# High-impact permissions: Admin always; Gestor only by explicit grant; other roles never.
GRANTABLE = {
    "settings:write",
    "stages:configure",
    "demo:reset",
    "permissions:manage",
    "integrations:configure",
    "agent:connect_professional",
    "automation:configure",
}

BASE_PERMS: dict[str, set[str]] = {
    "gestor": {
        "dashboard:read", "indicators:read", "crm:read", "crm:write", "crm:move_back",
        "crm:export", "services:read", "services:write", "users:read",
    },
    "atendente": {"crm:read", "crm:write", "services:read", "indicators:read", "users:read"},
    "profissional": {"services:read", "indicators:read"},
    "financeiro": {"dashboard:read", "indicators:read", "services:read"},
    "estoque": {"services:read", "indicators:read"},
}
BASE_PERMS["admin"] = set().union(*BASE_PERMS.values()) | GRANTABLE


def effective_permissions(user: dict) -> set[str]:
    role = user.get("role")
    perms = set(BASE_PERMS.get(role, set()))
    if role == "gestor":
        perms |= set(user.get("permissions") or []) & GRANTABLE
    return perms


@dataclass
class Principal:
    user: dict
    clinic: dict
    perms: set[str] = field(default_factory=set)

    @property
    def user_id(self) -> str:
        return self.user["id"]

    @property
    def clinic_id(self) -> str:
        return self.clinic["id"]

    @property
    def role(self) -> str:
        return self.user["role"]

    def can(self, perm: str) -> bool:
        return perm in self.perms


async def get_principal(request: Request) -> Principal:
    """Re-derives user, clinic and permissions from the database on every request."""
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Não autenticado")
    session = await db.sessions.find_one({"id": payload.get("sid"), "user_id": payload.get("sub")})
    if not session:
        raise HTTPException(status_code=401, detail="Sessão encerrada ou expirada")
    user = await db.users.find_one({"id": payload["sub"], "active": True}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuário inativo")
    clinic = await db.clinics.find_one({"id": user["clinic_id"]}, {"_id": 0})
    if not clinic:
        raise HTTPException(status_code=401, detail="Clínica não encontrada")
    return Principal(user=user, clinic=clinic, perms=effective_permissions(user))


def require(perm: str):
    async def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.can(perm):
            await db.audit_logs.insert_one({
                "clinic_id": principal.clinic_id, "user_id": principal.user_id,
                "action": "permission_denied", "details": {"permission": perm},
                "at": datetime.now(timezone.utc),
            })
            raise HTTPException(status_code=403, detail="Sem permissão para esta ação")
        return principal
    return dependency


class TenantRepo:
    """Every read/write is pinned to the principal's clinic. Never use db.<coll> for tenant data."""

    def __init__(self, principal: Principal):
        self.clinic_id = principal.clinic_id

    def _f(self, flt: dict | None = None) -> dict:
        return {**(flt or {}), "clinic_id": self.clinic_id}

    async def find(self, coll: str, flt: dict | None = None, sort: list | None = None,
                   skip: int = 0, limit: int = 0) -> list[dict]:
        cur = db[coll].find(self._f(flt), {"_id": 0})
        if sort:
            cur = cur.sort(sort)
        if skip:
            cur = cur.skip(skip)
        if limit:
            cur = cur.limit(limit)
        return await cur.to_list(length=limit or 10000)

    async def find_one(self, coll: str, flt: dict) -> dict | None:
        return await db[coll].find_one(self._f(flt), {"_id": 0})

    async def count(self, coll: str, flt: dict | None = None) -> int:
        return await db[coll].count_documents(self._f(flt))

    async def insert(self, coll: str, doc: dict) -> dict:
        doc = {**doc, "clinic_id": self.clinic_id}
        await db[coll].insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    async def update_one(self, coll: str, flt: dict, update: dict) -> Any:
        return await db[coll].update_one(self._f(flt), update)

    async def aggregate(self, coll: str, pipeline: list[dict]) -> list[dict]:
        return await db[coll].aggregate([{"$match": {"clinic_id": self.clinic_id}}, *pipeline]).to_list(10000)


async def audit(clinic_id: str, user_id: str | None, action: str, entity: str | None = None,
                entity_id: str | None = None, details: dict | None = None) -> None:
    """Minimal audit trail — never store passwords, tokens or message contents here."""
    await db.audit_logs.insert_one({
        "clinic_id": clinic_id, "user_id": user_id, "action": action, "entity": entity,
        "entity_id": entity_id, "details": details or {}, "at": datetime.now(timezone.utc),
    })
