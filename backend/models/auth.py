import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class SignupIn(BaseModel):
    clinic_name: str = Field(min_length=2, max_length=120)
    owner_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("clinic_name", "owner_name")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Informe ao menos 2 caracteres")
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("A senha deve conter letras e números")
        return v


class StageConfig(BaseModel):
    code: str
    label: str
    color: str


class ClinicOut(BaseModel):
    id: str
    name: str
    currency: str
    timezone: str
    is_demo: bool
    show_lost: bool
    stages: list[StageConfig]
    created_at: datetime


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    role_label: str
    granted_permissions: list[str]


class MeOut(BaseModel):
    user: UserOut
    clinic: ClinicOut
    permissions: list[str]


class DemoAccount(BaseModel):
    email: str
    role: str
    role_label: str


class DemoInfoOut(BaseModel):
    enabled: bool
    accounts: list[DemoAccount]
    password: str | None = None


class MemberOut(BaseModel):
    id: str
    name: str
    role: str
    role_label: str
