from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from models.common import Channel, Consent, StageCode, Temperature


def _clean_tags(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    out: list[str] = []
    for t in v:
        t = t.strip().lower()
        if not t:
            continue
        if len(t) > 30:
            raise ValueError("Etiquetas têm no máximo 30 caracteres")
        if t not in out:
            out.append(t)
    if len(out) > 10:
        raise ValueError("Máximo de 10 etiquetas")
    return out


class ContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    channel: Channel = "whatsapp"
    service_interest_id: str | None = None
    owner_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    consent: Consent = "nao_informado"

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        return _clean_tags(v) or []


class ContactUpdate(BaseModel):
    expected_version: int
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=254)
    channel: Channel | None = None
    service_interest_id: str | None = None
    owner_id: str | None = None
    tags: list[str] | None = None
    consent: Consent | None = None
    temperature: Temperature | None = None
    next_action: str | None = Field(default=None, max_length=300)
    next_action_date: datetime | None = None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: list[str] | None) -> list[str] | None:
        return _clean_tags(v)


class MoveIn(BaseModel):
    to_stage: StageCode
    expected_version: int
    loss_reason: str | None = Field(default=None, max_length=300)
    exception_confirmed: bool = False
    exception_reason: str | None = Field(default=None, max_length=300)
    reason: str | None = Field(default=None, max_length=300)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class InteractionIn(BaseModel):
    summary: str = Field(min_length=2, max_length=500)


class Note(BaseModel):
    id: str
    text: str
    author_id: str | None = None
    author_name: str
    created_at: datetime


class Contact(BaseModel):
    id: str
    name: str
    phone: str
    email: str
    channel: str
    service_interest_id: str | None
    service_interest_name: str | None = None
    owner_id: str | None
    owner_name: str | None = None
    stage: str
    tags: list[str]
    notes: list[Note]
    consent: str
    temperature: str | None = None
    next_action: str | None = None
    next_action_date: datetime | None = None
    loss_reason: str | None = None
    is_demo: bool
    entered_at: datetime
    last_interaction_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime


class ContactListOut(BaseModel):
    items: list[Contact]
    total: int
    page: int
    page_size: int


class BoardColumn(BaseModel):
    code: str
    label: str
    color: str
    count: int
    items: list[Contact]


class BoardOut(BaseModel):
    columns: list[BoardColumn]
    total: int


class ContactEvent(BaseModel):
    id: str
    contact_id: str
    type: str  # created | stage_change | updated | interaction
    from_stage: str | None = None
    to_stage: str | None = None
    origin: str  # manual | automatico | ia | demo
    user_id: str | None = None
    user_name: str | None = None
    at: datetime
    loss_reason: str | None = None
    exception_confirmed: bool = False
    exception_reason: str | None = None
    reason: str | None = None
    is_backward: bool = False
    summary: str | None = None
