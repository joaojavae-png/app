from typing import Literal

from pydantic import BaseModel

StageCode = Literal[
    "iniciou_conversa", "conversando", "consulta_agendada",
    "consulta_realizada", "paciente_recorrente", "perdido",
]
Channel = Literal["whatsapp", "instagram", "telefone", "indicacao", "site", "presencial", "outro"]
Consent = Literal["opt_in", "opt_out", "nao_informado"]
Temperature = Literal["frio", "morno", "quente"]


class OkOut(BaseModel):
    ok: bool = True
    message: str | None = None
