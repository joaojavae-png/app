import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError

from lib.authz import ROLE_LABELS, Principal, audit, get_principal
from lib.db import db
from lib.demo import DEMO_USERS, default_clinic, demo_enabled
import os
from lib.security import (COOKIE_NAME, clear_session_cookie, create_token, decode_token, hash_password,
                          new_session, set_session_cookie, verify_password)
from models.auth import ClinicOut, DemoAccount, DemoInfoOut, LoginIn, MeOut, SignupIn, UserOut
from models.common import OkOut

router = APIRouter(prefix="/auth", tags=["auth"])

_failed: dict[str, list[float]] = {}
MAX_ATTEMPTS, WINDOW_S = 5, 900


def build_me(principal: Principal) -> MeOut:
    u, c = principal.user, principal.clinic
    return MeOut(
        user=UserOut(id=u["id"], name=u["name"], email=u["email"], role=u["role"],
                     role_label=ROLE_LABELS[u["role"]], granted_permissions=u.get("permissions") or []),
        clinic=ClinicOut(**c),
        permissions=sorted(principal.perms),
    )


async def _start_session(user: dict, response: Response) -> None:
    sid, expires = new_session()
    await db.sessions.insert_one({"id": sid, "user_id": user["id"], "clinic_id": user["clinic_id"],
                                  "created_at": datetime.now(timezone.utc), "expires_at": expires})
    set_session_cookie(response, create_token(user["id"], sid, expires))


async def _principal_for(user: dict) -> Principal:
    from lib.authz import effective_permissions
    clinic = await db.clinics.find_one({"id": user["clinic_id"]}, {"_id": 0})
    return Principal(user=user, clinic=clinic, perms=effective_permissions(user))


@router.post("/login", response_model=MeOut)
async def login(body: LoginIn, response: Response):
    email = body.email.strip().lower()
    now = time.time()
    attempts = [t for t in _failed.get(email, []) if now - t < WINDOW_S]
    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 15 minutos e tente novamente.")
    user = await db.users.find_one({"email": email, "active": True}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        attempts.append(now)
        _failed[email] = attempts
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    _failed.pop(email, None)
    await _start_session(user, response)
    await audit(user["clinic_id"], user["id"], "login")
    return build_me(await _principal_for(user))


@router.post("/signup", response_model=MeOut, status_code=201)
async def signup(body: SignupIn, response: Response):
    """Creates a NEW clinic and its first Admin. Never attaches to an existing clinic."""
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado. Faça login ou use outro e-mail.")
    clinic = default_clinic(body.clinic_name, is_demo=False)
    user = {
        "id": str(uuid.uuid4()), "clinic_id": clinic["id"], "email": email, "name": body.owner_name,
        "role": "admin", "permissions": [], "password_hash": hash_password(body.password), "active": True,
        "is_demo": False, "created_at": datetime.now(timezone.utc),
    }
    await db.clinics.insert_one(dict(clinic))
    try:
        await db.users.insert_one(dict(user))
    except DuplicateKeyError:
        await db.clinics.delete_one({"id": clinic["id"]})
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado. Faça login ou use outro e-mail.")
    user.pop("_id", None)
    await _start_session(user, response)
    await audit(clinic["id"], user["id"], "clinic_signup", "clinic", clinic["id"])
    return build_me(await _principal_for(user))


@router.post("/logout", response_model=OkOut)
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_token(token) if token else None
    if payload:
        await db.sessions.delete_one({"id": payload.get("sid")})
    clear_session_cookie(response)
    return OkOut(message="Sessão encerrada")


@router.get("/me", response_model=MeOut)
async def me(principal: Principal = Depends(get_principal)):
    return build_me(principal)


@router.get("/demo-info", response_model=DemoInfoOut)
async def demo_info():
    if not demo_enabled():
        return DemoInfoOut(enabled=False, accounts=[])
    return DemoInfoOut(
        enabled=True,
        accounts=[DemoAccount(email=e, role=r, role_label=ROLE_LABELS[r]) for e, _, r, _ in DEMO_USERS],
        password=os.environ.get("DEMO_PASSWORD"),
    )
