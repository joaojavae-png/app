"""Demo clinic: fictitious data, flagged is_demo, isolated in its own clinic_id.

Only active when DEMO_MODE=true. Reset touches ONLY documents whose clinic_id is the demo clinic.
"""

import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from lib.db import db
from lib.funnel import DEFAULT_STAGES, LINEAR_STAGES
from lib.security import hash_password

DEMO_SLUG = "demo-vatrexz"
DEMO_USERS = [
    ("admin@demo.vatrexz.com", "Ana Demo (Admin)", "admin", []),
    ("gestor@demo.vatrexz.com", "Bruno Demo (Gestor)", "gestor", ["stages:configure"]),
    ("atendente@demo.vatrexz.com", "Carla Demo (Atendente)", "atendente", []),
    ("profissional@demo.vatrexz.com", "Diego Demo (Profissional)", "profissional", []),
]

DEMO_SERVICES = [
    ("Avaliação estética inicial", "Avaliação", 45, 15000),
    ("Limpeza de pele", "Facial", 60, 18000),
    ("Peeling químico superficial", "Facial", 45, 25000),
    ("Microagulhamento", "Facial", 60, 45000),
    ("Aplicação de toxina botulínica", "Injetáveis", 30, 120000),
    ("Preenchimento labial", "Injetáveis", 45, 150000),
    ("Drenagem linfática", "Corporal", 60, 16000),
    ("Depilação a laser — sessão", "Corporal", 30, 22000),
]

FIRST = ["Mariana", "Juliana", "Patrícia", "Fernanda", "Camila", "Renata", "Beatriz", "Larissa", "Aline",
         "Tatiane", "Gabriela", "Vanessa", "Luana", "Priscila", "Débora", "Rafael", "Thiago", "Lucas",
         "Gustavo", "Rodrigo", "Helena", "Isabela", "Sofia", "Valéria", "Monique", "Paula", "Elaine",
         "Natália", "Sabrina", "Viviane"]
LAST = ["Fictícia", "Exemplo", "Modelo", "Teste", "Simulada"]
CHANNELS = ["whatsapp", "whatsapp", "whatsapp", "instagram", "indicacao", "site", "telefone"]
TAGS = ["promoção", "retorno", "indicação", "vip", "orçamento"]
# final stage distribution for the 30 demo contacts
FINAL = (["iniciou_conversa"] * 7 + ["conversando"] * 7 + ["consulta_agendada"] * 6
         + ["consulta_realizada"] * 4 + ["paciente_recorrente"] * 3 + ["perdido"] * 3)
LOSS_REASONS = ["DEMO — informou que não tem interesse no momento",
                "DEMO — preferiu outra clínica", "DEMO — orçamento acima do esperado"]


def demo_enabled() -> bool:
    return os.environ.get("DEMO_MODE", "false").lower() == "true"


def default_clinic(name: str, is_demo: bool) -> dict:
    return {
        "id": str(uuid.uuid4()), "name": name, "currency": "BRL", "timezone": "America/Sao_Paulo",
        "is_demo": is_demo, "show_lost": True, "stages": [dict(s) for s in DEFAULT_STAGES],
        "created_at": datetime.now(timezone.utc),
    }


async def ensure_demo() -> None:
    if not demo_enabled():
        return
    clinic = await db.clinics.find_one({"slug": DEMO_SLUG})
    if clinic is None:
        clinic = {**default_clinic("Clínica Demonstração Vatrexz (DEMO)", True), "slug": DEMO_SLUG}
        await db.clinics.insert_one(dict(clinic))
    password_hash = hash_password(os.environ["DEMO_PASSWORD"])
    for email, name, role, perms in DEMO_USERS:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({
                "id": str(uuid.uuid4()), "clinic_id": clinic["id"], "email": email, "name": name,
                "role": role, "permissions": perms, "password_hash": password_hash, "active": True,
                "is_demo": True, "created_at": datetime.now(timezone.utc),
            })
    if await db.contacts.count_documents({"clinic_id": clinic["id"]}) == 0:
        await seed_demo_data(clinic["id"])


async def seed_demo_data(clinic_id: str) -> None:
    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    users = await db.users.find({"clinic_id": clinic_id, "role": {"$in": ["admin", "gestor", "atendente"]}}).to_list(10)
    services = []
    for name, cat, dur, price in DEMO_SERVICES:
        svc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id, "name": name,
            "description": "Descrição demonstrativa (DEMO). Não constitui protocolo ou recomendação clínica.",
            "category": cat, "duration_min": dur, "price_cents": price, "status": "ativo",
            "operational_notes": "", "is_demo": True, "created_at": now, "updated_at": now,
        }
        services.append(svc)
    await db.services.insert_many([dict(s) for s in services])

    contacts, events = [], []
    for i, final in enumerate(FINAL):
        entered = now - timedelta(days=rng.randint(0, 75), hours=rng.randint(0, 20))
        cid = str(uuid.uuid4())
        owner = rng.choice(users + [None, None]) if users else None
        svc = rng.choice(services + [None])
        path = ["iniciou_conversa"]
        if final == "perdido":
            path += LINEAR_STAGES[1:rng.randint(1, 3)] + ["perdido"]
        else:
            path = LINEAR_STAGES[: LINEAR_STAGES.index(final) + 1]
        t = entered
        prev = None
        for step in path:
            if prev is not None:
                t = min(t + timedelta(days=rng.randint(1, 6), hours=rng.randint(1, 9)), now)
            is_appt_stage = step in ("consulta_agendada", "consulta_realizada", "paciente_recorrente")
            events.append({
                "id": str(uuid.uuid4()), "clinic_id": clinic_id, "contact_id": cid,
                "type": "created" if prev is None else "stage_change", "from_stage": prev, "to_stage": step,
                "origin": "demo", "user_id": None, "user_name": "Carga de demonstração", "at": t,
                "loss_reason": LOSS_REASONS[i % 3] if step == "perdido" else None,
                "exception_confirmed": is_appt_stage,
                "exception_reason": "DEMO — agendamento fictício; módulo Agenda disponível na Fase 2" if is_appt_stage else None,
                "reason": None, "is_backward": False, "summary": None, "is_demo": True,
            })
            prev = step
        next_action, next_date = None, None
        if final in ("iniciou_conversa", "conversando") and rng.random() < 0.7:
            next_action = "DEMO — retornar contato e enviar informações solicitadas"
            next_date = now + timedelta(days=rng.randint(-4, 5))
        if final == "consulta_agendada" and i % 3 == 0:
            next_action = "DEMO — follow-up: não compareceu ao agendamento fictício"
            next_date = now - timedelta(days=1)
        notes = []
        if final == "consulta_agendada" and i % 3 == 0:
            notes.append({"id": str(uuid.uuid4()), "text": "DEMO — registrada falta no agendamento fictício. Mantida a etapa e criada próxima ação de follow-up.",
                          "author_id": None, "author_name": "Carga de demonstração", "created_at": t})
        contacts.append({
            "id": cid, "clinic_id": clinic_id, "name": f"{FIRST[i]} {LAST[i % len(LAST)]}",
            "phone": f"(11) 90000-{i:04d}", "email": f"contato{i:02d}@exemplo.com.br",
            "channel": rng.choice(CHANNELS), "service_interest_id": svc["id"] if svc else None,
            "owner_id": owner["id"] if owner else None, "stage": final,
            "tags": rng.sample(TAGS, rng.randint(0, 2)), "notes": notes,
            "consent": rng.choice(["opt_in", "nao_informado", "opt_in"]),
            "temperature": None, "next_action": next_action, "next_action_date": next_date,
            "loss_reason": LOSS_REASONS[i % 3] if final == "perdido" else None,
            "is_demo": True, "entered_at": entered, "last_interaction_at": t,
            "version": 1, "created_at": entered, "updated_at": t,
        })
    await db.contacts.insert_many(contacts)
    await db.contact_events.insert_many(events)


async def reset_demo(clinic_id: str) -> None:
    """Restores the demo clinic. Hard guard: refuses any clinic that is not flagged is_demo."""
    clinic = await db.clinics.find_one({"id": clinic_id})
    if not clinic or not clinic.get("is_demo"):
        raise ValueError("not a demo clinic")
    for coll in ("contacts", "contact_events", "services"):
        await db[coll].delete_many({"clinic_id": clinic_id})
    await db.clinics.update_one({"id": clinic_id}, {"$set": {
        "name": "Clínica Demonstração Vatrexz (DEMO)", "currency": "BRL", "timezone": "America/Sao_Paulo",
        "show_lost": True, "stages": [dict(s) for s in DEFAULT_STAGES],
    }})
    await seed_demo_data(clinic_id)
