"""CRM funnel: stable stage codes and transition rules. Display names/colors live on the clinic."""

LINEAR_STAGES = [
    "iniciou_conversa",
    "conversando",
    "consulta_agendada",
    "consulta_realizada",
    "paciente_recorrente",
]
LOST = "perdido"
STAGE_CODES = LINEAR_STAGES + [LOST]
ORDER = {code: i for i, code in enumerate(LINEAR_STAGES)}

DEFAULT_STAGES = [
    {"code": "iniciou_conversa", "label": "Iniciou Conversa", "color": "#3B82F6"},
    {"code": "conversando", "label": "Conversando", "color": "#06B6D4"},
    {"code": "consulta_agendada", "label": "Agendou", "color": "#8B5CF6"},
    {"code": "consulta_realizada", "label": "Compareceu", "color": "#10B981"},
    {"code": "paciente_recorrente", "label": "Cliente Recorrente", "color": "#20B8A6"},
    {"code": "perdido", "label": "Perdido / Sem interesse", "color": "#EF4444"},
]

# Entering these stages requires a linked appointment. The Agenda module is Phase 2, so in
# Phase 1 the move is only accepted with an explicit, justified exception.
REQUIRES_APPOINTMENT = {"consulta_agendada", "consulta_realizada", "paciente_recorrente"}

LEAD_STAGES = ["iniciou_conversa", "conversando", "consulta_agendada"]
CLIENT_STAGES = ["consulta_realizada", "paciente_recorrente"]


def is_backward(from_stage: str, to_stage: str) -> bool:
    """Leaving 'perdido' (reopening) counts as a backward move; entering it does not."""
    if from_stage == LOST:
        return True
    if to_stage == LOST:
        return False
    return ORDER[to_stage] < ORDER[from_stage]


def can_auto_transition(from_stage: str, to_stage: str) -> bool:
    """Automatic rules (Phase 2+: agenda/conversations) may only advance along the linear funnel."""
    if LOST in (from_stage, to_stage):
        return False
    return ORDER[to_stage] > ORDER[from_stage]


def reached_set(target: str) -> list[str]:
    """Stages that count as having reached `target` (target or any later linear stage)."""
    return LINEAR_STAGES[ORDER[target]:]
