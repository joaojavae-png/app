"""Period presets resolved server-side in the clinic's timezone; bounds returned in UTC."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

PRESETS = {"today", "7d", "30d", "month", "all", "custom"}
PRESET_LABELS = {
    "today": "Hoje", "7d": "Últimos 7 dias", "30d": "Últimos 30 dias",
    "month": "Este mês", "all": "Todo o período", "custom": "Intervalo personalizado",
}


def _local_start(d: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, time.min, tzinfo=tz).astimezone(timezone.utc)


def resolve_period(preset: str, start: str | None, end: str | None, tz_name: str) -> tuple[datetime | None, datetime | None]:
    """Returns [start, end) in UTC, or (None, None) for 'all'."""
    if preset not in PRESETS:
        raise HTTPException(status_code=422, detail="Período inválido")
    if preset == "all":
        return None, None
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    if preset == "custom":
        try:
            s, e = date.fromisoformat(start or ""), date.fromisoformat(end or "")
        except ValueError:
            raise HTTPException(status_code=422, detail="Informe datas de início e fim válidas (AAAA-MM-DD)")
        if s > e:
            raise HTTPException(status_code=422, detail="A data inicial deve ser anterior ou igual à final")
        return _local_start(s, tz), _local_start(e + timedelta(days=1), tz)
    if preset == "today":
        s = today
    elif preset == "7d":
        s = today - timedelta(days=6)
    elif preset == "30d":
        s = today - timedelta(days=29)
    else:  # month
        s = today.replace(day=1)
    return _local_start(s, tz), _local_start(today + timedelta(days=1), tz)


def date_range_filter(field: str, start: datetime | None, end: datetime | None) -> dict:
    if start is None or end is None:
        return {}
    return {field: {"$gte": start, "$lt": end}}
