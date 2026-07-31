"""Date/time helpers — calendar dates in America/Sao_Paulo."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("America/Sao_Paulo")


def today_sp() -> date:
    """Current calendar date in São Paulo."""
    return datetime.now(APP_TZ).date()


def to_sp_calendar_date(dt: datetime | date | None) -> date | None:
    """Convert aware/naive datetime or date to SP calendar date."""
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TZ).date()


def normalize_date_only_value(value: object) -> date | None:
    """Parse YYYY-MM-DD or ISO datetime strings as calendar dates (no TZ shift)."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return to_sp_calendar_date(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if "T" in raw:
            raw = raw.split("T")[0]
        return date.fromisoformat(raw[:10])
    return value  # type: ignore[return-value]


def deadline_input_to_utc(value: object) -> datetime | None:
    """Store date-only deadlines at noon SP (avoids off-by-one in Brazil)."""
    calendar = normalize_date_only_value(value)
    if calendar is None:
        return None
    local_noon = datetime.combine(calendar, time(12, 0), tzinfo=APP_TZ)
    return local_noon.astimezone(timezone.utc)


def format_date_only_iso(dt: datetime | date | None) -> str | None:
    """API output for date-only fields (YYYY-MM-DD in SP)."""
    calendar = to_sp_calendar_date(dt) if isinstance(dt, datetime) else dt
    if calendar is None:
        return None
    return calendar.isoformat()


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)
