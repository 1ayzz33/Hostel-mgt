"""Small shared helpers for timestamps, validation and presentation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import CATEGORIES, PRIORITIES, SLA_HOURS
from .errors import ApiError

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(ISO_FORMAT)


def now_iso() -> str:
    return iso(utc_now())


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def sla_due_at(created_at: str, priority: str) -> str:
    created = parse_iso(created_at) or utc_now()
    hours = SLA_HOURS.get(priority, SLA_HOURS["medium"])
    return iso(created + timedelta(hours=hours))


def is_overdue(report: dict) -> bool:
    if report.get("status") in ("resolved", "closed"):
        return False
    created = parse_iso(report.get("created_at"))
    if not created:
        return False
    hours = SLA_HOURS.get(report.get("priority", "medium"), 48)
    return utc_now() > created + timedelta(hours=hours)


def require_text(value, field: str, *, min_len: int = 1, max_len: int = 500) -> str:
    if not isinstance(value, str):
        raise ApiError(400, f"{field} is required.")
    cleaned = value.strip()
    if len(cleaned) < min_len:
        raise ApiError(400, f"{field} must be at least {min_len} characters.")
    if len(cleaned) > max_len:
        raise ApiError(400, f"{field} must be {max_len} characters or fewer.")
    return cleaned


def check_choice(value, options, field: str):
    if value not in options:
        raise ApiError(400, f"{field} must be one of: {', '.join(options)}.")
    return value


def parse_positive_int(value, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"{field} must be a whole number.") from None
    if parsed <= 0:
        raise ApiError(400, f"{field} must be greater than zero.")
    return parsed


def validate_report_payload(payload: dict) -> dict:
    title = require_text(payload.get("title"), "Title", min_len=5, max_len=120)
    description = require_text(
        payload.get("description"), "Description", min_len=15, max_len=4000
    )
    location = require_text(payload.get("location"), "Location", min_len=2, max_len=120)
    category = check_choice(payload.get("category"), CATEGORIES, "Category")
    priority = check_choice(payload.get("priority", "medium"), PRIORITIES, "Priority")
    return {
        "title": title,
        "description": description,
        "location": location,
        "category": category,
        "priority": priority,
    }


def serialise_report(report: dict) -> dict:
    item = dict(report)
    item["sla_due_at"] = sla_due_at(item["created_at"], item["priority"])
    item["is_overdue"] = is_overdue(item)
    item["rating"] = item.get("rating")
    # Avoid shipping base64 photos inside list responses; detail endpoints add it.
    item.pop("photo", None)
    return item
