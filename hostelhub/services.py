"""Business logic for HostelHub.

Every function receives an open SQLite connection so the HTTP layer stays thin
and the same code can be exercised directly by the automated test suite.
"""
from __future__ import annotations

import base64
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone

from .config import (
    CATEGORIES,
    MAX_PHOTO_BYTES,
    PRIORITIES,
    ROLES,
    SESSION_DAYS,
    SLA_HOURS,
    STATUSES,
)
from .errors import ApiError
from .security import (
    hash_password,
    hash_token,
    new_session_token,
    normalise_email,
    valid_email,
    verify_password,
)
from .utils import (
    check_choice,
    iso,
    is_overdue,
    now_iso,
    parse_iso,
    parse_positive_int,
    require_text,
    serialise_report,
    utc_now,
    validate_report_payload,
)

PHOTO_RE = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)$")
OPEN_STATUSES = ("submitted", "assigned", "in_progress", "reopened")
UNRESOLVED_STATUSES = OPEN_STATUSES


# ---------------------------------------------------------------------------
# Users and authentication
# ---------------------------------------------------------------------------

def public_user(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    user = dict(row)
    user.pop("password_hash", None)
    user["is_active"] = bool(user.get("is_active", 1))
    return user


def _fetch_user(conn: sqlite3.Connection, user_id: int) -> dict:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise ApiError(404, "User not found.")
    return dict(row)


def create_user(conn: sqlite3.Connection, payload: dict, *, allow_roles: bool = False) -> dict:
    full_name = require_text(payload.get("full_name"), "Full name", min_len=3, max_len=80)
    email = normalise_email(str(payload.get("email", "")))
    if not valid_email(email):
        raise ApiError(400, "Enter a valid email address.")
    password = payload.get("password") or ""
    if len(password) < 8:
        raise ApiError(400, "Password must be at least 8 characters.")
    if len(password) > 128:
        raise ApiError(400, "Password must be 128 characters or fewer.")
    role = payload.get("role", "student")
    if not allow_roles:
        role = "student"
    check_choice(role, ROLES, "Role")

    student_id = (payload.get("student_id") or "").strip() or None
    if role == "student" and not student_id:
        raise ApiError(400, "Matriculation number is required for students.")
    if student_id and conn.execute(
        "SELECT 1 FROM users WHERE student_id = ? COLLATE NOCASE", (student_id,)
    ).fetchone():
        raise ApiError(409, "That matriculation number is already registered.")

    hostel_id = payload.get("hostel_id")
    if hostel_id in ("", None):
        hostel_id = None
    else:
        hostel_id = parse_positive_int(hostel_id, "Hostel")
        if not conn.execute("SELECT 1 FROM hostels WHERE id = ?", (hostel_id,)).fetchone():
            raise ApiError(404, "Selected hostel does not exist.")

    department = (payload.get("department") or "").strip()
    phone = (payload.get("phone") or "").strip()
    room_number = (payload.get("room_number") or "").strip()
    now = now_iso()
    try:
        cur = conn.execute(
            """INSERT INTO users
               (full_name, email, password_hash, role, student_id, phone, hostel_id,
                room_number, department, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                full_name,
                email,
                hash_password(password),
                role,
                student_id,
                phone,
                hostel_id,
                room_number,
                department,
                now,
                now,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ApiError(409, "An account with that email already exists.") from None
    return public_user(_fetch_user(conn, cur.lastrowid))


def authenticate(conn: sqlite3.Connection, email: str, password: str) -> dict:
    email = normalise_email(email or "")
    row = conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    if not row or not verify_password(password or "", row["password_hash"]):
        raise ApiError(401, "Incorrect email or password.")
    if not row["is_active"]:
        raise ApiError(403, "This account has been deactivated. Contact the hostel administrator.")
    return public_user(row)


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = new_session_token()
    now = utc_now()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            hash_token(token),
            user_id,
            iso(now),
            iso(now + timedelta(days=SESSION_DAYS)),
            iso(now),
        ),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (iso(now),))
    conn.commit()
    return token


def resolve_session(conn: sqlite3.Connection, token: str | None) -> dict | None:
    if not token:
        return None
    row = conn.execute(
        """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1""",
        (hash_token(token), now_iso()),
    ).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE sessions SET last_seen = ? WHERE token_hash = ?",
        (now_iso(), hash_token(token)),
    )
    conn.commit()
    return dict(row)


def revoke_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
        conn.commit()


def get_meta(conn: sqlite3.Connection, user: dict) -> dict:
    hostels = [dict(r) for r in conn.execute("SELECT * FROM hostels ORDER BY name")]
    facilities = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM facilities ORDER BY hostel_id, name"
        )
    ]
    staff = []
    if user["role"] == "admin":
        staff = [
            dict(r)
            for r in conn.execute(
                """SELECT u.id, u.full_name, u.email, u.department,
                          (SELECT COUNT(*) FROM reports r
                           WHERE r.assigned_to = u.id AND r.status IN
                           ('assigned','in_progress','reopened')) AS active_load
                   FROM users u WHERE u.role = 'staff' AND u.is_active = 1
                   ORDER BY u.full_name"""
            )
        ]
    return {
        "hostels": hostels,
        "facilities": facilities,
        "staff": staff,
        "categories": CATEGORIES,
        "priorities": PRIORITIES,
        "statuses": STATUSES,
        "sla_hours": SLA_HOURS,
    }


# ---------------------------------------------------------------------------
# Hostels, facilities and announcements
# ---------------------------------------------------------------------------

def create_hostel(conn: sqlite3.Connection, payload: dict) -> dict:
    name = require_text(payload.get("name"), "Hostel name", min_len=3, max_len=100)
    code = require_text(payload.get("code"), "Hostel code", min_len=2, max_len=12).upper()
    gender = check_choice(payload.get("gender", "Mixed"), ["Male", "Female", "Mixed"], "Gender")
    total_rooms = int(payload.get("total_rooms") or 0)
    if total_rooms < 0 or total_rooms > 5000:
        raise ApiError(400, "Total rooms must be between 0 and 5000.")
    try:
        cur = conn.execute(
            """INSERT INTO hostels
               (name, code, gender, address, warden_name, warden_phone, total_rooms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                code,
                gender,
                (payload.get("address") or "").strip(),
                (payload.get("warden_name") or "").strip(),
                (payload.get("warden_phone") or "").strip(),
                total_rooms,
                now_iso(),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ApiError(409, "A hostel with that code already exists.") from None
    return dict(conn.execute("SELECT * FROM hostels WHERE id = ?", (cur.lastrowid,)).fetchone())


def update_hostel(conn: sqlite3.Connection, hostel_id: int, payload: dict) -> dict:
    hostel = conn.execute("SELECT * FROM hostels WHERE id = ?", (hostel_id,)).fetchone()
    if not hostel:
        raise ApiError(404, "Hostel not found.")
    fields = {}
    if "name" in payload:
        fields["name"] = require_text(payload["name"], "Hostel name", min_len=3, max_len=100)
    if "code" in payload:
        code = require_text(payload["code"], "Hostel code", min_len=2, max_len=12).upper()
        existing = conn.execute(
            "SELECT 1 FROM hostels WHERE code = ? AND id != ?", (code, hostel_id)
        ).fetchone()
        if existing:
            raise ApiError(409, "A hostel with that code already exists.")
        fields["code"] = code
    if "gender" in payload:
        fields["gender"] = check_choice(payload["gender"], ["Male", "Female", "Mixed"], "Gender")
    if "address" in payload:
        fields["address"] = (payload.get("address") or "").strip()
    for key, label in (("warden_name", "Warden name"), ("warden_phone", "Warden phone")):
        if key in payload:
            fields[key] = (payload.get(key) or "").strip()
    if "total_rooms" in payload:
        try:
            rooms = int(payload["total_rooms"])
        except (TypeError, ValueError):
            raise ApiError(400, "Total rooms must be a whole number.") from None
        if rooms < 0 or rooms > 5000:
            raise ApiError(400, "Total rooms must be between 0 and 5000.")
        fields["total_rooms"] = rooms
    if not fields:
        return dict(hostel)
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE hostels SET {assignments} WHERE id = ?", (*fields.values(), hostel_id)
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM hostels WHERE id = ?", (hostel_id,)).fetchone())


def create_facility(conn: sqlite3.Connection, payload: dict) -> dict:
    hostel_id = parse_positive_int(payload.get("hostel_id"), "Hostel")
    if not conn.execute("SELECT 1 FROM hostels WHERE id = ?", (hostel_id,)).fetchone():
        raise ApiError(404, "Hostel not found.")
    name = require_text(payload.get("name"), "Facility name", min_len=2, max_len=100)
    category = check_choice(payload.get("category"), CATEGORIES, "Category")
    condition = check_choice(
        payload.get("condition", "Good"),
        ["Good", "Fair", "Poor", "Under repair"],
        "Condition",
    )
    cur = conn.execute(
        """INSERT INTO facilities (hostel_id, name, category, location, condition, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (hostel_id, name, category, (payload.get("location") or "").strip(), condition, now_iso()),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM facilities WHERE id = ?", (cur.lastrowid,)).fetchone())


def update_facility(conn: sqlite3.Connection, facility_id: int, payload: dict) -> dict:
    facility = conn.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,)).fetchone()
    if not facility:
        raise ApiError(404, "Facility not found.")
    fields = {}
    if "name" in payload:
        fields["name"] = require_text(payload["name"], "Facility name", min_len=2, max_len=100)
    if "location" in payload:
        fields["location"] = (payload.get("location") or "").strip()
    if "category" in payload:
        fields["category"] = check_choice(payload["category"], CATEGORIES, "Category")
    if "condition" in payload:
        fields["condition"] = check_choice(
            payload["condition"], ["Good", "Fair", "Poor", "Under repair"], "Condition"
        )
    if not fields:
        return dict(facility)
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE facilities SET {assignments} WHERE id = ?",
        (*fields.values(), facility_id),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,)).fetchone())


# ---------------------------------------------------------------------------
# Notifications and timeline
# ---------------------------------------------------------------------------

def _notify(
    conn: sqlite3.Connection,
    user_id: int | None,
    title: str,
    message: str,
    report_id: int | None = None,
) -> None:
    if not user_id:
        return
    conn.execute(
        """INSERT INTO notifications (user_id, report_id, title, message, is_read, created_at)
           VALUES (?, ?, ?, ?, 0, ?)""",
        (user_id, report_id, title, message, now_iso()),
    )


def _notify_admins(conn: sqlite3.Connection, title: str, message: str, report_id: int) -> None:
    admins = conn.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = 1").fetchall()
    for admin in admins:
        _notify(conn, admin["id"], title, message, report_id)


def _add_update(
    conn: sqlite3.Connection,
    report_id: int,
    user_id: int | None,
    action: str,
    note: str = "",
    from_status: str | None = None,
    to_status: str | None = None,
    is_internal: bool = False,
) -> None:
    conn.execute(
        """INSERT INTO report_updates
           (report_id, user_id, action, note, from_status, to_status, is_internal, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (report_id, user_id, action, note, from_status, to_status, int(is_internal), now_iso()),
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

REPORT_SELECT = """
SELECT r.*, h.name AS hostel_name, h.code AS hostel_code, h.address AS hostel_address,
       s.full_name AS student_name, s.email AS student_email, s.phone AS student_phone,
       s.student_id AS student_number, s.room_number AS student_room,
       a.full_name AS staff_name, a.email AS staff_email
FROM reports r
JOIN hostels h ON h.id = r.hostel_id
JOIN users s ON s.id = r.student_id
LEFT JOIN users a ON a.id = r.assigned_to
"""


def _validate_photo(photo) -> str | None:
    if not photo:
        return None
    if not isinstance(photo, str):
        raise ApiError(400, "Photo must be an image data URL.")
    match = PHOTO_RE.match(photo)
    if not match:
        raise ApiError(400, "Photo must be a PNG, JPEG or WebP image.")
    encoded = re.sub(r"\s+", "", match.group(2))
    try:
        size = len(base64.b64decode(encoded, validate=True))
    except (ValueError, TypeError):
        raise ApiError(400, "Photo data is not valid base64.") from None
    if size > MAX_PHOTO_BYTES:
        raise ApiError(413, "Photo must be 2 MB or smaller.")
    return f"data:image/{match.group(1)};base64,{encoded}"


def create_report(conn: sqlite3.Connection, student: dict, payload: dict) -> dict:
    if student["role"] != "student":
        raise ApiError(403, "Only students can submit facility reports.")
    data = validate_report_payload(payload)
    hostel_id = payload.get("hostel_id") or student.get("hostel_id")
    hostel_id = parse_positive_int(hostel_id, "Hostel")
    hostel = conn.execute("SELECT * FROM hostels WHERE id = ?", (hostel_id,)).fetchone()
    if not hostel:
        raise ApiError(404, "Hostel not found.")

    facility_id = payload.get("facility_id")
    if facility_id in ("", None):
        facility_id = None
    else:
        facility_id = parse_positive_int(facility_id, "Facility")
        facility = conn.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,)).fetchone()
        if not facility:
            raise ApiError(404, "Facility not found.")
        if facility["hostel_id"] != hostel_id:
            raise ApiError(400, "The selected facility is not in that hostel.")
        if payload.get("category") in (None, ""):
            data["category"] = facility["category"]

    photo = _validate_photo(payload.get("photo"))
    now = now_iso()
    cur = conn.execute(
        """INSERT INTO reports
           (student_id, hostel_id, facility_id, category, title, description, location,
            priority, status, photo, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?)""",
        (
            student["id"],
            hostel_id,
            facility_id,
            data["category"],
            data["title"],
            data["description"],
            data["location"],
            data["priority"],
            photo,
            now,
            now,
        ),
    )
    report_id = cur.lastrowid
    ref = f"HFR-{utc_now().year}-{report_id:04d}"
    conn.execute("UPDATE reports SET ref = ? WHERE id = ?", (ref, report_id))
    _add_update(
        conn, report_id, student["id"], "created",
        "Report submitted and queued for review.", None, "submitted",
    )
    _notify(
        conn, student["id"], "Report received",
        f"{ref} has been submitted. You will be notified as it progresses.", report_id,
    )
    _notify_admins(
        conn, "New facility report",
        f"{ref}: {data['title']} ({hostel['name']}).", report_id,
    )
    conn.commit()
    return get_report(conn, student, report_id)


def _can_view(user: dict, report: dict) -> bool:
    if user["role"] == "admin":
        return True
    if user["role"] == "student":
        return report["student_id"] == user["id"]
    return report["assigned_to"] == user["id"]


def _get_report_row(conn: sqlite3.Connection, report_id: int) -> dict:
    row = conn.execute(REPORT_SELECT + " WHERE r.id = ?", (report_id,)).fetchone()
    if not row:
        raise ApiError(404, "Report not found.")
    return dict(row)


def _capabilities(user: dict, report: dict) -> dict:
    role = user["role"]
    status = report["status"]
    owned = report["student_id"] == user["id"]
    assigned = report["assigned_to"] == user["id"]
    return {
        "can_assign": role == "admin" and status != "closed",
        "can_start": role == "staff" and assigned and status in ("assigned", "reopened"),
        "can_resolve": (
            (role == "staff" and assigned and status in ("assigned", "in_progress", "reopened"))
            or (role == "admin" and status in ("assigned", "in_progress", "reopened"))
        ),
        "can_close": (
            (role == "student" and owned and status == "resolved")
            or (role == "admin" and status in ("resolved", "in_progress", "assigned"))
        ),
        "can_reopen": role == "student" and owned and status in ("resolved", "closed"),
        "can_feedback": role == "student" and owned and status in ("resolved", "closed")
        and report.get("rating") is None,
        "can_comment": _can_view(user, report),
    }


def get_report(conn: sqlite3.Connection, user: dict, report_id: int) -> dict:
    report = _get_report_row(conn, report_id)
    if not _can_view(user, report):
        raise ApiError(403, "You do not have access to this report.")
    item = serialise_report(report)
    item["photo"] = report.get("photo")
    item["hostel"] = {
        "id": report["hostel_id"],
        "name": report["hostel_name"],
        "code": report["hostel_code"],
        "address": report["hostel_address"],
    }
    item["student"] = {
        "id": report["student_id"],
        "full_name": report["student_name"],
        "email": report["student_email"],
        "phone": report["student_phone"],
        "student_id": report["student_number"],
        "room_number": report["student_room"],
    }
    item["staff"] = (
        {
            "id": report["assigned_to"],
            "full_name": report["staff_name"],
            "email": report["staff_email"],
        }
        if report.get("assigned_to")
        else None
    )
    updates = conn.execute(
        """SELECT ru.*, u.full_name AS author_name, u.role AS author_role
           FROM report_updates ru LEFT JOIN users u ON u.id = ru.user_id
           WHERE ru.report_id = ? ORDER BY ru.created_at ASC, ru.id ASC""",
        (report_id,),
    ).fetchall()
    item["updates"] = [
        {**dict(row), "is_internal": bool(row["is_internal"])}
        for row in updates
        if user["role"] != "student" or not row["is_internal"]
    ]
    item["capabilities"] = _capabilities(user, report)
    return item


def list_reports(conn: sqlite3.Connection, user: dict, filters: dict) -> dict:
    clauses = []
    params: list = []
    if user["role"] == "student":
        clauses.append("r.student_id = ?")
        params.append(user["id"])
    elif user["role"] == "staff":
        clauses.append("r.assigned_to = ?")
        params.append(user["id"])

    if filters.get("status"):
        check_choice(filters["status"], STATUSES, "Status")
        clauses.append("r.status = ?")
        params.append(filters["status"])
    if filters.get("priority"):
        check_choice(filters["priority"], PRIORITIES, "Priority")
        clauses.append("r.priority = ?")
        params.append(filters["priority"])
    if filters.get("category"):
        check_choice(filters["category"], CATEGORIES, "Category")
        clauses.append("r.category = ?")
        params.append(filters["category"])
    if filters.get("hostel_id"):
        clauses.append("r.hostel_id = ?")
        params.append(parse_positive_int(filters["hostel_id"], "Hostel"))
    if filters.get("assigned_to"):
        clauses.append("r.assigned_to = ?")
        params.append(parse_positive_int(filters["assigned_to"], "Staff"))
    query = filters.get("q", "").strip()
    if query:
        clauses.append(
            "(r.ref LIKE ? OR r.title LIKE ? OR r.location LIKE ? "
            "OR s.full_name LIKE ? OR r.description LIKE ?)"
        )
        params.extend([f"%{query}%"] * 5)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = [
        dict(row)
        for row in conn.execute(
            REPORT_SELECT + where + " ORDER BY r.created_at DESC, r.id DESC LIMIT 500",
            params,
        )
    ]
    items = [serialise_report(row) for row in rows]
    if filters.get("overdue") in ("1", "true", True):
        items = [item for item in items if item["is_overdue"]]
    if filters.get("open") in ("1", "true", True):
        items = [item for item in items if item["status"] in OPEN_STATUSES]

    total = len(items)
    try:
        page = max(1, int(filters.get("page", 1)))
        per_page = min(100, max(1, int(filters.get("per_page", 50))))
    except (TypeError, ValueError):
        page, per_page = 1, 50
    start = (page - 1) * per_page
    return {
        "items": items[start : start + per_page],
        "total": total,
        "page": page,
        "per_page": per_page,
        "summary": dict(Counter(item["status"] for item in items)),
    }


def assign_report(
    conn: sqlite3.Connection, admin: dict, report_id: int, staff_id: int, note: str = ""
) -> dict:
    if admin["role"] != "admin":
        raise ApiError(403, "Only administrators can assign reports.")
    report = _get_report_row(conn, report_id)
    if report["status"] == "closed":
        raise ApiError(409, "Closed reports cannot be reassigned. Reopen the report first.")
    staff_id = parse_positive_int(staff_id, "Staff member")
    staff = conn.execute(
        "SELECT * FROM users WHERE id = ? AND role = 'staff'", (staff_id,)
    ).fetchone()
    if not staff or not staff["is_active"]:
        raise ApiError(404, "Select an active maintenance staff member.")
    old_status = report["status"]
    new_status = "assigned" if old_status in ("submitted", "reopened") else old_status
    conn.execute(
        "UPDATE reports SET assigned_to = ?, status = ?, updated_at = ? WHERE id = ?",
        (staff_id, new_status, now_iso(), report_id),
    )
    _add_update(
        conn, report_id, admin["id"], "assigned",
        note.strip() or f"Assigned to {staff['full_name']}.", old_status, new_status,
    )
    _notify(
        conn, staff_id, "Report assigned to you",
        f"{report['ref']} – {report['title']} is now in your queue.", report_id,
    )
    _notify(
        conn, report["student_id"], "Report assigned",
        f"{report['ref']} has been assigned to {staff['full_name']}.", report_id,
    )
    conn.commit()
    return get_report(conn, admin, report_id)


def change_status(
    conn: sqlite3.Connection, user: dict, report_id: int, target: str, note: str = ""
) -> dict:
    report = _get_report_row(conn, report_id)
    if not _can_view(user, report):
        raise ApiError(403, "You do not have access to this report.")
    check_choice(target, STATUSES, "Status")
    current = report["status"]
    role = user["role"]
    note = (note or "").strip()
    now = now_iso()

    if target == "closed":
        if role == "student":
            if report["student_id"] != user["id"] or current != "resolved":
                raise ApiError(403, "You can only close your own resolved report.")
        elif role != "admin":
            raise ApiError(403, "Only the student or an administrator can close this report.")
        if current not in ("resolved", "assigned", "in_progress"):
            raise ApiError(409, "This report cannot be closed from its current status.")
    elif target == "reopened":
        if role != "student" or report["student_id"] != user["id"]:
            raise ApiError(403, "Only the student who filed the report can reopen it.")
        if current not in ("resolved", "closed"):
            raise ApiError(409, "Only resolved or closed reports can be reopened.")
        if len(note) < 5:
            raise ApiError(400, "Please explain why the issue is being reopened.")
    elif target == "in_progress":
        if role not in ("staff", "admin"):
            raise ApiError(403, "Only maintenance staff or administrators can start work.")
        if role == "staff" and report["assigned_to"] != user["id"]:
            raise ApiError(403, "This report is not assigned to you.")
        if current not in ("assigned", "reopened"):
            raise ApiError(409, "Only assigned or reopened reports can be started.")
        if not report["assigned_to"]:
            raise ApiError(409, "Assign the report to a staff member first.")
    elif target == "resolved":
        if role not in ("staff", "admin"):
            raise ApiError(403, "Only maintenance staff or administrators can resolve reports.")
        if role == "staff" and report["assigned_to"] != user["id"]:
            raise ApiError(403, "This report is not assigned to you.")
        if current not in ("assigned", "in_progress", "reopened"):
            raise ApiError(409, "This report cannot be resolved from its current status.")
        if len(note) < 10:
            raise ApiError(400, "Add a resolution note of at least 10 characters.")
    elif target == "assigned":
        raise ApiError(400, "Use the assignment action to assign a staff member.")
    else:
        raise ApiError(400, "That status change is not supported.")

    updates = {"status": target, "updated_at": now}
    if target == "resolved":
        updates.update({"resolved_at": now, "resolution_note": note, "rating": None, "feedback": None})
    if target == "reopened":
        updates.update({"resolved_at": None, "resolution_note": None, "rating": None, "feedback": None})
    assignments = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(
        f"UPDATE reports SET {assignments} WHERE id = ?", (*updates.values(), report_id)
    )
    _add_update(conn, report_id, user["id"], target, note, current, target)

    actor = "Administrator" if role == "admin" else (
        "Maintenance staff" if role == "staff" else "Student"
    )
    if target == "in_progress":
        _notify(
            conn, report["student_id"], "Work has started",
            f"{report['ref']} is now being worked on.", report_id,
        )
    elif target == "resolved":
        _notify(
            conn, report["student_id"], "Report resolved",
            f"{report['ref']} has been marked resolved. Please rate the service.", report_id,
        )
        _notify_admins(
            conn, "Report resolved", f"{report['ref']} was resolved by {actor}.", report_id,
        )
    elif target == "closed":
        _notify(
            conn, report["assigned_to"], "Report closed",
            f"{report['ref']} has been closed by the student.", report_id,
        )
    elif target == "reopened":
        _notify(
            conn, report["assigned_to"], "Report reopened",
            f"{report['ref']} was reopened: {note}", report_id,
        )
        _notify_admins(
            conn, "Report reopened", f"{report['ref']} was reopened by the student.", report_id,
        )
    conn.commit()
    return get_report(conn, user, report_id)


def add_comment(
    conn: sqlite3.Connection, user: dict, report_id: int, note: str, internal: bool = False
) -> dict:
    report = _get_report_row(conn, report_id)
    if not _can_view(user, report):
        raise ApiError(403, "You do not have access to this report.")
    note = require_text(note, "Comment", min_len=2, max_len=2000)
    if internal and user["role"] == "student":
        raise ApiError(403, "Students cannot post internal notes.")
    _add_update(conn, report_id, user["id"], "comment", note, None, None, is_internal=internal)
    conn.execute("UPDATE reports SET updated_at = ? WHERE id = ?", (now_iso(), report_id))
    if not internal:
        if user["id"] != report["student_id"]:
            _notify(
                conn, report["student_id"], "New comment",
                f"{user['full_name']} commented on {report['ref']}.", report_id,
            )
        if report["assigned_to"] and user["id"] != report["assigned_to"]:
            _notify(
                conn, report["assigned_to"], "New comment",
                f"{user['full_name']} commented on {report['ref']}.", report_id,
            )
    conn.commit()
    return get_report(conn, user, report_id)


def submit_feedback(
    conn: sqlite3.Connection, student: dict, report_id: int, rating, feedback: str = ""
) -> dict:
    report = _get_report_row(conn, report_id)
    if report["student_id"] != student["id"] or student["role"] != "student":
        raise ApiError(403, "Only the student who filed the report can rate it.")
    if report["status"] not in ("resolved", "closed"):
        raise ApiError(409, "You can rate the service after the report is resolved.")
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise ApiError(400, "Rating must be between 1 and 5.") from None
    if rating < 1 or rating > 5:
        raise ApiError(400, "Rating must be between 1 and 5.")
    feedback = (feedback or "").strip()
    if len(feedback) > 1000:
        raise ApiError(400, "Feedback must be 1000 characters or fewer.")
    conn.execute(
        "UPDATE reports SET rating = ?, feedback = ?, updated_at = ? WHERE id = ?",
        (rating, feedback, now_iso(), report_id),
    )
    _add_update(
        conn, report_id, student["id"], "feedback",
        feedback or f"Rated {rating} out of 5.", None, None,
    )
    if report["assigned_to"]:
        _notify(
            conn, report["assigned_to"], "New service rating",
            f"{report['ref']} received a {rating}/5 rating.", report_id,
        )
    conn.commit()
    return get_report(conn, student, report_id)


# ---------------------------------------------------------------------------
# Notifications and announcements
# ---------------------------------------------------------------------------

def list_notifications(conn: sqlite3.Connection, user: dict) -> dict:
    rows = conn.execute(
        """SELECT * FROM notifications WHERE user_id = ?
           ORDER BY created_at DESC, id DESC LIMIT 100""",
        (user["id"],),
    ).fetchall()
    items = [{**dict(row), "is_read": bool(row["is_read"])} for row in rows]
    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],)
    ).fetchone()[0]
    return {"items": items, "unread": unread}


def mark_notifications(conn: sqlite3.Connection, user: dict, notification_id=None) -> dict:
    if notification_id:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (parse_positive_int(notification_id, "Notification"), user["id"]),
        )
    else:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
    conn.commit()
    return list_notifications(conn, user)


def list_announcements(conn: sqlite3.Connection, user: dict) -> list[dict]:
    audience = {"student": "students", "staff": "staff", "admin": "admin"}.get(user["role"], "all")
    rows = conn.execute(
        """SELECT a.*, u.full_name AS author_name FROM announcements a
           LEFT JOIN users u ON u.id = a.created_by
           WHERE a.audience IN ('all', ?)
           ORDER BY a.is_pinned DESC, a.created_at DESC LIMIT 30""",
        (audience,),
    ).fetchall()
    return [{**dict(row), "is_pinned": bool(row["is_pinned"])} for row in rows]


def create_announcement(conn: sqlite3.Connection, admin: dict, payload: dict) -> dict:
    if admin["role"] != "admin":
        raise ApiError(403, "Only administrators can publish announcements.")
    title = require_text(payload.get("title"), "Title", min_len=4, max_len=120)
    body = require_text(payload.get("body"), "Message", min_len=10, max_len=3000)
    audience = check_choice(
        payload.get("audience", "all"), ["all", "students", "staff", "admin"], "Audience"
    )
    cur = conn.execute(
        """INSERT INTO announcements (title, body, audience, is_pinned, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, body, audience, int(bool(payload.get("is_pinned"))), admin["id"], now_iso()),
    )
    conn.commit()
    row = conn.execute(
        """SELECT a.*, u.full_name AS author_name FROM announcements a
           LEFT JOIN users u ON u.id = a.created_by WHERE a.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    return {**dict(row), "is_pinned": bool(row["is_pinned"])}


def delete_announcement(conn: sqlite3.Connection, admin: dict, announcement_id: int) -> None:
    if admin["role"] != "admin":
        raise ApiError(403, "Only administrators can delete announcements.")
    cur = conn.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    if cur.rowcount == 0:
        raise ApiError(404, "Announcement not found.")
    conn.commit()


# ---------------------------------------------------------------------------
# Dashboard and analytics
# ---------------------------------------------------------------------------

def _resolution_hours(report: dict) -> float | None:
    start, end = parse_iso(report.get("created_at")), parse_iso(report.get("resolved_at"))
    if not start or not end:
        return None
    return round((end - start).total_seconds() / 3600, 1)


def _open_query(conn: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[dict]:
    rows = conn.execute(REPORT_SELECT + (" WHERE " + where if where else ""), params).fetchall()
    return [serialise_report(dict(row)) for row in rows]


def build_dashboard(conn: sqlite3.Connection, user: dict) -> dict:
    role = user["role"]
    notifications = list_notifications(conn, user)
    announcements = list_announcements(conn, user)
    payload: dict = {
        "role": role,
        "announcements": announcements[:3],
        "unread_notifications": notifications["unread"],
    }

    if role == "student":
        rows = _open_query(conn, "r.student_id = ?", (user["id"],))
        counts = Counter(row["status"] for row in rows)
        rated = [row["rating"] for row in rows if row.get("rating")]
        payload.update(
            {
                "stats": {
                    "total": len(rows),
                    "open": sum(counts[s] for s in OPEN_STATUSES),
                    "in_progress": counts["in_progress"],
                    "resolved": counts["resolved"] + counts["closed"],
                    "overdue": sum(1 for row in rows if row["is_overdue"]),
                    "average_rating": round(sum(rated) / len(rated), 1) if rated else None,
                },
                "recent": rows[:6],
                "attention": [row for row in rows if row["is_overdue"]][:4],
            }
        )
    elif role == "staff":
        rows = _open_query(conn, "r.assigned_to = ?", (user["id"],))
        counts = Counter(row["status"] for row in rows)
        month_start = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        resolved_rows = [row for row in rows if row.get("resolved_at")]
        resolved_this_month = sum(
            1 for row in resolved_rows
            if (parse_iso(row["resolved_at"]) or datetime.min.replace(tzinfo=timezone.utc))
            >= month_start
        )
        rated = [row["rating"] for row in rows if row.get("rating")]
        payload.update(
            {
                "stats": {
                    "assigned": len(rows),
                    "active": sum(counts[s] for s in OPEN_STATUSES),
                    "in_progress": counts["in_progress"],
                    "resolved_this_month": resolved_this_month,
                    "overdue": sum(1 for row in rows if row["is_overdue"]),
                    "average_rating": round(sum(rated) / len(rated), 1) if rated else None,
                },
                "recent": rows[:8],
                "attention": [row for row in rows if row["is_overdue"]][:4],
            }
        )
    else:
        rows = _open_query(conn)
        counts = Counter(row["status"] for row in rows)
        resolved = [row for row in rows if row.get("status") in ("resolved", "closed")]
        hours = [h for h in (_resolution_hours(row) for row in resolved) if h is not None]
        rated = [row["rating"] for row in rows if row.get("rating")]
        month_start = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        resolved_this_month = sum(
            1 for row in resolved
            if (parse_iso(row["resolved_at"]) or datetime.min.replace(tzinfo=timezone.utc))
            >= month_start
        )
        staff_rows = conn.execute(
            """SELECT u.id, u.full_name, u.department, u.email,
                      COUNT(r.id) AS assigned,
                      SUM(CASE WHEN r.status IN ('assigned','in_progress','reopened') THEN 1 ELSE 0 END) AS active
               FROM users u LEFT JOIN reports r ON r.assigned_to = u.id
               WHERE u.role = 'staff' AND u.is_active = 1
               GROUP BY u.id ORDER BY active DESC, u.full_name"""
        ).fetchall()
        payload.update(
            {
                "stats": {
                    "total": len(rows),
                    "open": sum(counts[s] for s in OPEN_STATUSES),
                    "overdue": sum(1 for row in rows if row["is_overdue"]),
                    "resolved_this_month": resolved_this_month,
                    "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
                    "average_rating": round(sum(rated) / len(rated), 1) if rated else None,
                },
                "recent": rows[:8],
                "attention": [row for row in rows if row["is_overdue"]][:5],
                "staff": [dict(row) for row in staff_rows],
            }
        )
    return payload


def build_analytics(conn: sqlite3.Connection, user: dict) -> dict:
    if user["role"] != "admin":
        raise ApiError(403, "Analytics are available to administrators only.")
    rows = _open_query(conn)
    status_counts = Counter(row["status"] for row in rows)
    priority_counts = Counter(row["priority"] for row in rows)

    categories = []
    for category in CATEGORIES:
        items = [row for row in rows if row["category"] == category]
        categories.append(
            {
                "category": category,
                "total": len(items),
                "open": sum(1 for row in items if row["status"] in OPEN_STATUSES),
            }
        )
    hostels = []
    for hostel in conn.execute("SELECT * FROM hostels ORDER BY name"):
        items = [row for row in rows if row["hostel_id"] == hostel["id"]]
        hostels.append(
            {
                "id": hostel["id"],
                "name": hostel["name"],
                "code": hostel["code"],
                "total": len(items),
                "open": sum(1 for row in items if row["status"] in OPEN_STATUSES),
            }
        )

    resolved = [row for row in rows if row["status"] in ("resolved", "closed")]
    hours = [h for h in (_resolution_hours(row) for row in resolved) if h is not None]
    within_sla = 0
    for row in resolved:
        created = parse_iso(row["created_at"])
        resolved_at = parse_iso(row["resolved_at"])
        if created and resolved_at:
            if resolved_at <= created + timedelta(hours=SLA_HOURS.get(row["priority"], 48)):
                within_sla += 1
    rated = [row["rating"] for row in rows if row.get("rating")]

    trend = []
    today = utc_now()
    for offset in range(5, -1, -1):
        month = (today.replace(day=1) - timedelta(days=offset * 28)).replace(day=1)
        if month.month == 12:
            next_month = month.replace(year=month.year + 1, month=1, day=1)
        else:
            next_month = month.replace(month=month.month + 1, day=1)
        submitted = sum(
            1 for row in rows
            if (parse_iso(row["created_at"]) or today) >= month
            and (parse_iso(row["created_at"]) or today) < next_month
        )
        resolved_in_month = sum(
            1 for row in rows
            if row.get("resolved_at")
            and (parse_iso(row["resolved_at"]) or today) >= month
            and (parse_iso(row["resolved_at"]) or today) < next_month
        )
        trend.append(
            {"month": month.strftime("%b"), "submitted": submitted, "resolved": resolved_in_month}
        )

    staff = []
    for member in conn.execute(
        """SELECT id, full_name, email, department FROM users
           WHERE role = 'staff' AND is_active = 1 ORDER BY full_name"""
    ):
        assigned = [row for row in rows if row["assigned_to"] == member["id"]]
        completed = [row for row in assigned if row["status"] in ("resolved", "closed")]
        member_hours = [h for h in (_resolution_hours(row) for row in completed) if h is not None]
        member_ratings = [row["rating"] for row in assigned if row.get("rating")]
        staff.append(
            {
                "id": member["id"],
                "full_name": member["full_name"],
                "department": member["department"],
                "assigned": len(assigned),
                "completed": len(completed),
                "active": sum(1 for row in assigned if row["status"] in OPEN_STATUSES),
                "avg_hours": round(sum(member_hours) / len(member_hours), 1) if member_hours else None,
                "rating": round(sum(member_ratings) / len(member_ratings), 1)
                if member_ratings else None,
            }
        )

    return {
        "totals": {
            "reports": len(rows),
            "open": sum(status_counts[s] for s in OPEN_STATUSES),
            "overdue": sum(1 for row in rows if row["is_overdue"]),
            "resolved": len(resolved),
            "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
            "sla_compliance": round(within_sla / len(resolved) * 100, 1) if resolved else None,
            "satisfaction": round(sum(rated) / len(rated), 1) if rated else None,
            "ratings": len(rated),
        },
        "by_status": [{"status": s, "count": status_counts[s]} for s in STATUSES],
        "by_priority": [
            {"priority": p, "count": priority_counts[p]} for p in ("urgent", "high", "medium", "low")
        ],
        "by_category": categories,
        "by_hostel": hostels,
        "trend": trend,
        "staff": staff,
    }


# ---------------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------------

def list_users(conn: sqlite3.Connection, admin: dict, filters: dict) -> list[dict]:
    if admin["role"] != "admin":
        raise ApiError(403, "Administrator access required.")
    clauses, params = [], []
    if filters.get("role"):
        check_choice(filters["role"], ROLES, "Role")
        clauses.append("u.role = ?")
        params.append(filters["role"])
    if filters.get("q"):
        clauses.append("(u.full_name LIKE ? OR u.email LIKE ? OR u.student_id LIKE ?)")
        params.extend([f"%{filters['q']}%"] * 3)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"""SELECT u.*, h.name AS hostel_name,
                   (SELECT COUNT(*) FROM reports r WHERE r.student_id = u.id)
                     AS reports_count,
                   (SELECT COUNT(*) FROM reports r WHERE r.assigned_to = u.id
                      AND r.status IN ('assigned','in_progress','reopened')) AS active_load
            FROM users u LEFT JOIN hostels h ON h.id = u.hostel_id
            {where} ORDER BY u.role, u.full_name""",
        params,
    ).fetchall()
    users = []
    for row in rows:
        item = public_user(row)
        item["hostel_name"] = row["hostel_name"]
        item["reports_count"] = row["reports_count"]
        item["active_load"] = row["active_load"]
        users.append(item)
    return users


def admin_create_user(conn: sqlite3.Connection, admin: dict, payload: dict) -> dict:
    if admin["role"] != "admin":
        raise ApiError(403, "Administrator access required.")
    return create_user(conn, payload, allow_roles=True)


def admin_update_user(
    conn: sqlite3.Connection, admin: dict, user_id: int, payload: dict
) -> dict:
    if admin["role"] != "admin":
        raise ApiError(403, "Administrator access required.")
    target = _fetch_user(conn, user_id)
    fields: dict = {}
    if "full_name" in payload:
        fields["full_name"] = require_text(payload["full_name"], "Full name", 3, 80)
    if "role" in payload:
        role = check_choice(payload["role"], ROLES, "Role")
        if target["id"] == admin["id"] and role != "admin":
            raise ApiError(409, "You cannot remove your own administrator role.")
        if target["role"] == "admin" and role != "admin":
            admins = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()[0]
            if admins <= 1:
                raise ApiError(409, "At least one active administrator is required.")
        fields["role"] = role
    if "is_active" in payload:
        active = bool(payload["is_active"])
        if target["id"] == admin["id"] and not active:
            raise ApiError(409, "You cannot deactivate your own account.")
        if target["role"] == "admin" and not active:
            admins = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()[0]
            if admins <= 1:
                raise ApiError(409, "At least one active administrator is required.")
        fields["is_active"] = int(active)
        if not active:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (target["id"],))
    for key in ("phone", "department", "room_number"):
        if key in payload:
            fields[key] = (payload.get(key) or "").strip()
    if "hostel_id" in payload:
        value = payload.get("hostel_id")
        if value in ("", None):
            fields["hostel_id"] = None
        else:
            hostel_id = parse_positive_int(value, "Hostel")
            if not conn.execute("SELECT 1 FROM hostels WHERE id = ?", (hostel_id,)).fetchone():
                raise ApiError(404, "Hostel not found.")
            fields["hostel_id"] = hostel_id
    if payload.get("password"):
        password = payload["password"]
        if len(password) < 8:
            raise ApiError(400, "Password must be at least 8 characters.")
        fields["password_hash"] = hash_password(password)
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (target["id"],))
    if not fields:
        return public_user(target)
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(f"UPDATE users SET {assignments} WHERE id = ?", (*fields.values(), user_id))
    conn.commit()
    return public_user(_fetch_user(conn, user_id))


def active_users_summary(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT role, COUNT(*) AS count FROM users WHERE is_active = 1 GROUP BY role"
    ).fetchall()
    return {row["role"]: row["count"] for row in rows}
