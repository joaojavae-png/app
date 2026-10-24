import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from lib.authz import Principal, TenantRepo, audit, require
from lib.funnel import CLIENT_STAGES, LEAD_STAGES, LOST, REQUIRES_APPOINTMENT, STAGE_CODES, is_backward
from lib.periods import date_range_filter, resolve_period
from models.contacts import (BoardColumn, BoardOut, Contact, ContactCreate, ContactEvent, ContactListOut,
                             ContactUpdate, InteractionIn, MoveIn, NoteIn)

router = APIRouter(prefix="/contacts", tags=["contacts"])

SORT_FIELDS = {"name", "entered_at", "last_interaction_at", "stage"}


class ContactFilters:
    def __init__(
        self,
        period: str = "all", start: str | None = None, end: str | None = None,
        date_basis: Literal["entered_at", "last_interaction_at"] = "entered_at",
        q: str = "", owner_id: str | None = None, channel: str | None = None,
        service_id: str | None = None, tag: str | None = None, stage: str | None = None,
        segment: Literal["todos", "leads", "clientes"] = "todos",
        next_action: Literal["any", "overdue", "none"] = "any",
    ):
        self.period, self.start, self.end, self.date_basis = period, start, end, date_basis
        self.q, self.owner_id, self.channel, self.service_id = q, owner_id, channel, service_id
        self.tag, self.stage, self.segment, self.next_action = tag, stage, segment, next_action

    def mongo(self, tz: str) -> dict:
        s, e = resolve_period(self.period, self.start, self.end, tz)
        flt: dict = date_range_filter(self.date_basis, s, e)
        if self.q.strip():
            rx = {"$regex": re.escape(self.q.strip()), "$options": "i"}
            flt["$or"] = [{"name": rx}, {"phone": rx}, {"email": rx}]
        if self.owner_id:
            flt["owner_id"] = None if self.owner_id == "none" else self.owner_id
        if self.channel:
            flt["channel"] = self.channel
        if self.service_id:
            flt["service_interest_id"] = None if self.service_id == "none" else self.service_id
        if self.tag:
            flt["tags"] = self.tag.strip().lower()
        if self.next_action == "overdue":
            flt["next_action_date"] = {"$lt": datetime.now(timezone.utc)}
        elif self.next_action == "none":
            flt["next_action"] = None
        if self.segment == "leads":
            flt["stage"] = {"$in": LEAD_STAGES}
        elif self.segment == "clientes":
            flt["stage"] = {"$in": CLIENT_STAGES}
        if self.stage:
            if self.stage not in STAGE_CODES:
                raise HTTPException(status_code=422, detail="Etapa inválida")
            flt["stage"] = self.stage if "stage" not in flt or self.stage in flt["stage"]["$in"] else "__none__"
        return flt


async def _enrich(repo: TenantRepo, docs: list[dict]) -> list[Contact]:
    svc_ids = {d["service_interest_id"] for d in docs if d.get("service_interest_id")}
    owner_ids = {d["owner_id"] for d in docs if d.get("owner_id")}
    services = {s["id"]: s["name"] for s in await repo.find("services", {"id": {"$in": list(svc_ids)}})} if svc_ids else {}
    users = {u["id"]: u["name"] for u in await repo.find("users", {"id": {"$in": list(owner_ids)}})} if owner_ids else {}
    return [Contact(**d, service_interest_name=services.get(d.get("service_interest_id")),
                    owner_name=users.get(d.get("owner_id"))) for d in docs]


async def _get(repo: TenantRepo, id: str) -> dict:
    doc = await repo.find_one("contacts", {"id": id})
    if not doc:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    return doc


async def _validate_refs(repo: TenantRepo, owner_id: str | None, service_id: str | None) -> None:
    if owner_id and not await repo.find_one("users", {"id": owner_id, "active": True}):
        raise HTTPException(status_code=422, detail="Responsável inválido para esta clínica")
    if service_id and not await repo.find_one("services", {"id": service_id}):
        raise HTTPException(status_code=422, detail="Serviço inválido para esta clínica")


def _event(contact_id: str, principal: Principal | None, type_: str, **kw) -> dict:
    return {
        "id": str(uuid.uuid4()), "contact_id": contact_id, "type": type_,
        "origin": kw.pop("origin", "manual"),
        "user_id": principal.user_id if principal else None,
        "user_name": principal.user["name"] if principal else None,
        "at": datetime.now(timezone.utc), "from_stage": None, "to_stage": None, "loss_reason": None,
        "exception_confirmed": False, "exception_reason": None, "reason": None, "is_backward": False,
        "summary": None, "is_demo": False, **kw,
    }


def _conflict(current: Contact) -> JSONResponse:
    return JSONResponse(status_code=409, content={
        "detail": "Este contato foi alterado por outra pessoa. Os dados foram atualizados; revise e tente novamente.",
        "current": current.model_dump(mode="json"),
    })


@router.get("", response_model=ContactListOut)
async def list_contacts(
    filters: ContactFilters = Depends(),
    sort: str = "last_interaction_at", order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(require("crm:read")),
):
    if sort not in SORT_FIELDS:
        raise HTTPException(status_code=422, detail="Campo de ordenação inválido")
    repo = TenantRepo(principal)
    flt = filters.mongo(principal.clinic["timezone"])
    total = await repo.count("contacts", flt)
    docs = await repo.find("contacts", flt, sort=[(sort, 1 if order == "asc" else -1), ("id", 1)],
                           skip=(page - 1) * page_size, limit=page_size)
    return ContactListOut(items=await _enrich(repo, docs), total=total, page=page, page_size=page_size)


@router.get("/board", response_model=BoardOut)
async def board(filters: ContactFilters = Depends(), limit: int = Query(100, ge=1, le=200),
                principal: Principal = Depends(require("crm:read"))):
    repo = TenantRepo(principal)
    base = filters.mongo(principal.clinic["timezone"])
    clinic = principal.clinic
    columns, total = [], 0
    for st in clinic["stages"]:
        if st["code"] == LOST and not clinic.get("show_lost", True):
            continue
        if "stage" in base:
            wanted = base["stage"]
            allowed = wanted["$in"] if isinstance(wanted, dict) else [wanted]
            if st["code"] not in allowed:
                continue
        flt = {**base, "stage": st["code"]}
        count = await repo.count("contacts", flt)
        docs = await repo.find("contacts", flt, sort=[("last_interaction_at", -1), ("id", 1)], limit=limit)
        columns.append(BoardColumn(code=st["code"], label=st["label"], color=st["color"], count=count,
                                   items=await _enrich(repo, docs)))
        total += count
    return BoardOut(columns=columns, total=total)


def _csv_safe(value: object) -> str:
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


@router.get("/export.csv")
async def export_csv(filters: ContactFilters = Depends(), principal: Principal = Depends(require("crm:export"))):
    repo = TenantRepo(principal)
    flt = filters.mongo(principal.clinic["timezone"])
    contacts = await _enrich(repo, await repo.find("contacts", flt, sort=[("entered_at", -1), ("id", 1)]))
    labels = {s["code"]: s["label"] for s in principal.clinic["stages"]}
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id", "nome", "etapa_codigo", "etapa", "canal", "servico_interesse", "responsavel", "etiquetas",
                "data_entrada_utc", "ultima_interacao_utc", "demo"])
    for c in contacts:
        w.writerow([_csv_safe(v) for v in [
            c.id, c.name, c.stage, labels.get(c.stage, c.stage), c.channel, c.service_interest_name or "",
            c.owner_name or "", ",".join(c.tags), c.entered_at.isoformat(), c.last_interaction_at.isoformat(),
            "sim" if c.is_demo else "nao"]])
    await audit(principal.clinic_id, principal.user_id, "contacts_exported", "contact", None, {"rows": len(contacts)})
    return Response(content="\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="contatos.csv"',
                             "X-Total-Count": str(len(contacts))})


@router.post("", response_model=Contact, status_code=201)
async def create_contact(body: ContactCreate, principal: Principal = Depends(require("crm:write"))):
    repo = TenantRepo(principal)
    await _validate_refs(repo, body.owner_id, body.service_interest_id)
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()), **body.model_dump(), "name": body.name.strip(), "stage": "iniciou_conversa",
        "notes": [], "temperature": None, "next_action": None, "next_action_date": None, "loss_reason": None,
        "is_demo": False, "entered_at": now, "last_interaction_at": now, "version": 1,
        "created_at": now, "updated_at": now,
    }
    await repo.insert("contacts", doc)
    await repo.insert("contact_events", _event(doc["id"], principal, "created", to_stage="iniciou_conversa",
                                               summary="Primeiro contato registrado manualmente"))
    return (await _enrich(repo, [await _get(repo, doc["id"])]))[0]


@router.get("/{id}", response_model=Contact)
async def get_contact(id: str, principal: Principal = Depends(require("crm:read"))):
    repo = TenantRepo(principal)
    return (await _enrich(repo, [await _get(repo, id)]))[0]


@router.get("/{id}/events", response_model=list[ContactEvent])
async def get_events(id: str, principal: Principal = Depends(require("crm:read"))):
    repo = TenantRepo(principal)
    await _get(repo, id)
    events = await repo.find("contact_events", {"contact_id": id}, sort=[("at", -1)])
    return [ContactEvent(**e) for e in events]


@router.patch("/{id}", response_model=Contact)
async def update_contact(id: str, body: ContactUpdate, principal: Principal = Depends(require("crm:write"))):
    repo = TenantRepo(principal)
    doc = await _get(repo, id)
    changes = body.model_dump(exclude_unset=True)
    expected = changes.pop("expected_version")
    if doc["version"] != expected:
        return _conflict((await _enrich(repo, [doc]))[0])
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=422, detail="Nome é obrigatório")
    await _validate_refs(repo, changes.get("owner_id"), changes.get("service_interest_id"))
    if not changes:
        return (await _enrich(repo, [doc]))[0]
    changes["updated_at"] = datetime.now(timezone.utc)
    res = await repo.update_one("contacts", {"id": id, "version": expected}, {"$set": changes, "$inc": {"version": 1}})
    if res.matched_count == 0:
        return _conflict((await _enrich(repo, [await _get(repo, id)]))[0])
    fields = sorted(k for k in changes if k != "updated_at")
    await repo.insert("contact_events", _event(id, principal, "updated", summary="Campos alterados: " + ", ".join(fields)))
    return (await _enrich(repo, [await _get(repo, id)]))[0]


@router.post("/{id}/move", response_model=Contact)
async def move_contact(id: str, body: MoveIn, principal: Principal = Depends(require("crm:write"))):
    repo = TenantRepo(principal)
    doc = await _get(repo, id)
    frm, to = doc["stage"], body.to_stage
    if to == frm:
        raise HTTPException(status_code=400, detail="O contato já está nesta etapa")
    if doc["version"] != body.expected_version:
        return _conflict((await _enrich(repo, [doc]))[0])
    backward = is_backward(frm, to)
    if backward:
        if not principal.can("crm:move_back"):
            raise HTTPException(status_code=403, detail="Retroceder ou reabrir um contato exige permissão de Admin ou Gestor")
        if not (body.reason and len(body.reason.strip()) >= 3):
            raise HTTPException(status_code=422, detail="Informe a justificativa do retrocesso")
    if to == LOST and not (body.loss_reason and len(body.loss_reason.strip()) >= 3):
        raise HTTPException(status_code=422, detail="O motivo da perda é obrigatório")
    exception = False
    if to in REQUIRES_APPOINTMENT:
        # Phase 1 has no Agenda module, so no appointment can be linked: an explicit exception is mandatory.
        if not body.exception_confirmed or not (body.exception_reason and len(body.exception_reason.strip()) >= 3):
            raise HTTPException(status_code=422, detail="Sem agendamento vinculado (Agenda — Fase 2). Confirme a exceção e informe a justificativa.")
        exception = True
    now = datetime.now(timezone.utc)
    res = await repo.update_one(
        "contacts", {"id": id, "version": body.expected_version},
        {"$set": {"stage": to, "updated_at": now, "loss_reason": body.loss_reason.strip() if to == LOST else None},
         "$inc": {"version": 1}},
    )
    if res.matched_count == 0:
        return _conflict((await _enrich(repo, [await _get(repo, id)]))[0])
    await repo.insert("contact_events", _event(
        id, principal, "stage_change", from_stage=frm, to_stage=to, is_backward=backward,
        loss_reason=body.loss_reason.strip() if to == LOST else None,
        exception_confirmed=exception, exception_reason=body.exception_reason.strip() if exception else None,
        reason=body.reason.strip() if body.reason else None,
    ))
    return (await _enrich(repo, [await _get(repo, id)]))[0]


@router.post("/{id}/notes", response_model=Contact, status_code=201)
async def add_note(id: str, body: NoteIn, principal: Principal = Depends(require("crm:write"))):
    repo = TenantRepo(principal)
    await _get(repo, id)
    note = {"id": str(uuid.uuid4()), "text": body.text.strip(), "author_id": principal.user_id,
            "author_name": principal.user["name"], "created_at": datetime.now(timezone.utc)}
    await repo.update_one("contacts", {"id": id}, {"$push": {"notes": note}})
    return (await _enrich(repo, [await _get(repo, id)]))[0]


@router.post("/{id}/interactions", response_model=Contact, status_code=201)
async def add_interaction(id: str, body: InteractionIn, principal: Principal = Depends(require("crm:write"))):
    """Manual interaction log (Phase 1 has no connected channel)."""
    repo = TenantRepo(principal)
    await _get(repo, id)
    now = datetime.now(timezone.utc)
    await repo.update_one("contacts", {"id": id}, {"$set": {"last_interaction_at": now}})
    await repo.insert("contact_events", _event(id, principal, "interaction", summary=body.summary.strip()))
    return (await _enrich(repo, [await _get(repo, id)]))[0]
