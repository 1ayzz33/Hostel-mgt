"""JSON API dispatch for HostelHub."""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from . import services
from .config import APP_NAME, APP_TAGLINE
from .errors import ApiError
from .utils import parse_positive_int, require_text

REPORT_ID_RE = re.compile(r"^/api/reports/(\d+)$")
REPORT_ACTION_RE = re.compile(r"^/api/reports/(\d+)/(assign|status|comments|feedback)$")
NOTIFICATION_READ_RE = re.compile(r"^/api/notifications/read$")
USER_ID_RE = re.compile(r"^/api/admin/users/(\d+)$")
HOSTEL_ID_RE = re.compile(r"^/api/admin/hostels/(\d+)$")
FACILITY_ID_RE = re.compile(r"^/api/admin/facilities/(\d+)$")
ANNOUNCEMENT_ID_RE = re.compile(r"^/api/announcements/(\d+)$")


def _require_role(user: dict, *roles: str) -> None:
    if user["role"] not in roles:
        raise ApiError(403, "You do not have permission to perform this action.")


def dispatch(
    conn: sqlite3.Connection,
    method: str,
    path: str,
    query: dict[str, str],
    body: dict,
    user: dict | None,
    token: str | None,
) -> tuple[int, dict[str, Any], str | None]:
    """Return (status, payload, session_token_to_set)."""
    # ---------------------------------------------------------------- public
    if path == "/api/health" and method == "GET":
        return 200, {"status": "ok", "app": APP_NAME, "tagline": APP_TAGLINE}, None

    if path == "/api/auth/hostels" and method == "GET":
        rows = conn.execute(
            "SELECT id, name, code, gender FROM hostels ORDER BY name"
        ).fetchall()
        return 200, {"items": [dict(row) for row in rows]}, None

    if path == "/api/auth/register" and method == "POST":
        created = services.create_user(conn, body)
        session = services.create_session(conn, created["id"])
        return 201, {"user": created, "token": session}, session

    if path == "/api/auth/login" and method == "POST":
        email = str(body.get("email", ""))
        password = str(body.get("password", ""))
        authenticated = services.authenticate(conn, email, password)
        session = services.create_session(conn, authenticated["id"])
        return 200, {"user": authenticated, "token": session}, session

    if path == "/api/auth/logout" and method == "POST":
        services.revoke_session(conn, token)
        return 200, {"ok": True}, ""

    # ------------------------------------------------------------- protected
    if user is None:
        raise ApiError(401, "Please sign in to continue.")

    if path == "/api/auth/me" and method == "GET":
        return 200, {"user": services.public_user(user)}, None

    if path == "/api/meta" and method == "GET":
        return 200, services.get_meta(conn, user), None

    if path == "/api/dashboard" and method == "GET":
        return 200, services.build_dashboard(conn, user), None

    if path == "/api/analytics" and method == "GET":
        return 200, services.build_analytics(conn, user), None

    if path == "/api/reports":
        if method == "GET":
            return 200, services.list_reports(conn, user, query), None
        if method == "POST":
            return 201, services.create_report(conn, user, body), None
        raise ApiError(405, "Method not allowed.")

    match = REPORT_ID_RE.match(path)
    if match and method == "GET":
        return 200, services.get_report(conn, user, int(match.group(1))), None

    match = REPORT_ACTION_RE.match(path)
    if match and method == "POST":
        report_id = int(match.group(1))
        action = match.group(2)
        if action == "assign":
            _require_role(user, "admin")
            staff_id = parse_positive_int(body.get("staff_id"), "Staff member")
            note = str(body.get("note", ""))
            return 200, services.assign_report(conn, user, report_id, staff_id, note), None
        if action == "status":
            target = require_text(body.get("status"), "Status", max_len=30)
            note = str(body.get("note", ""))
            return 200, services.change_status(conn, user, report_id, target, note), None
        if action == "comments":
            note = require_text(body.get("note"), "Comment", min_len=2, max_len=2000)
            return 201, services.add_comment(
                conn, user, report_id, note, bool(body.get("internal"))
            ), None
        if action == "feedback":
            return 200, services.submit_feedback(
                conn, user, report_id, body.get("rating"), str(body.get("feedback", ""))
            ), None

    if path == "/api/notifications" and method == "GET":
        return 200, services.list_notifications(conn, user), None

    if NOTIFICATION_READ_RE.match(path) and method == "POST":
        return 200, services.mark_notifications(conn, user, body.get("id")), None

    if path == "/api/announcements":
        if method == "GET":
            return 200, {"items": services.list_announcements(conn, user)}, None
        if method == "POST":
            _require_role(user, "admin")
            return 201, services.create_announcement(conn, user, body), None
        raise ApiError(405, "Method not allowed.")

    match = ANNOUNCEMENT_ID_RE.match(path)
    if match and method == "DELETE":
        _require_role(user, "admin")
        services.delete_announcement(conn, user, int(match.group(1)))
        return 200, {"ok": True}, None

    if path == "/api/admin/users":
        _require_role(user, "admin")
        if method == "GET":
            return 200, {"items": services.list_users(conn, user, query)}, None
        if method == "POST":
            return 201, services.admin_create_user(conn, user, body), None
        raise ApiError(405, "Method not allowed.")

    match = USER_ID_RE.match(path)
    if match and method == "PATCH":
        _require_role(user, "admin")
        return 200, services.admin_update_user(conn, user, int(match.group(1)), body), None

    if path == "/api/admin/hostels":
        _require_role(user, "admin")
        if method == "GET":
            rows = conn.execute("SELECT * FROM hostels ORDER BY name").fetchall()
            return 200, {"items": [dict(row) for row in rows]}, None
        if method == "POST":
            return 201, services.create_hostel(conn, body), None
        raise ApiError(405, "Method not allowed.")

    match = HOSTEL_ID_RE.match(path)
    if match and method == "PATCH":
        _require_role(user, "admin")
        return 200, services.update_hostel(conn, int(match.group(1)), body), None

    if path == "/api/admin/facilities":
        _require_role(user, "admin")
        if method == "GET":
            rows = conn.execute(
                """SELECT f.*, h.name AS hostel_name, h.code AS hostel_code
                   FROM facilities f JOIN hostels h ON h.id = f.hostel_id
                   ORDER BY h.name, f.name"""
            ).fetchall()
            return 200, {"items": [dict(row) for row in rows]}, None
        if method == "POST":
            return 201, services.create_facility(conn, body), None
        raise ApiError(405, "Method not allowed.")

    match = FACILITY_ID_RE.match(path)
    if match and method == "PATCH":
        _require_role(user, "admin")
        return 200, services.update_facility(conn, int(match.group(1)), body), None

    raise ApiError(404, "API endpoint not found.")
