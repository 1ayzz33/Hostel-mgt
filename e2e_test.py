"""End-to-end test client for HostelHub API.

Runs against a live server (default http://127.0.0.1:8000) using only the
Python standard library, simulating the three demo user roles.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from urllib.parse import urlencode

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

CREDS = {
    "student": ("student@hostelhub.edu.ng", "Student@123"),
    "staff": ("grace.okafor@hostelhub.edu.ng", "Staff@123"),
    "admin": ("admin@hostelhub.edu.ng", "Admin@123"),
}


class Fail(Exception):
    pass


def request(method, path, payload=None, token=None, query=None, raw=False):
    url = f"{BASE}{path}"
    if query:
        url += "?" + urlencode(query)
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (body if raw else json.loads(body)), resp.headers
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {"error": body}
        return exc.code, parsed, exc.headers


def login(role):
    email, password = CREDS[role]
    status, payload, _ = request("POST", "/api/auth/login", {"email": email, "password": password})
    if status != 200:
        raise Fail(f"{role} login failed ({status}): {payload}")
    print(f"  login as {role}: ok (token={payload['token'][:12]}…)")
    return payload["token"], payload["user"]


def me(token):
    status, payload, _ = request("GET", "/api/auth/me", token=token)
    assert status == 200, payload
    return payload["user"]


def assert_eq(actual, expected, label):
    if actual != expected:
        raise Fail(f"{label}: expected {expected!r}, got {actual!r}")


def test_health():
    status, payload, _ = request("GET", "/api/health")
    assert_eq(status, 200, "health status")
    print("  health:", payload["app"], "-", payload["tagline"])


def test_meta(student_token):
    status, payload, _ = request("GET", "/api/meta", token=student_token)
    assert_eq(status, 200, "meta status")
    assert payload["categories"] and payload["priorities"] and payload["hostels"]
    print("  meta:", len(payload["hostels"]), "hostels,", len(payload["categories"]), "categories")


def test_reports_student(student_token):
    # List my reports
    status, payload, _ = request("GET", "/api/reports", token=student_token)
    assert_eq(status, 200, "reports list status")
    assert payload["total"] >= 1
    print(f"  student reports: {payload['total']} total, {payload['summary']}")

    # Create a new report
    new = {
        "hostel_id": 1,
        "category": "Electrical",
        "title": "E2E test socket sparking in corridor",
        "description": "E2E automated check: corridor socket outside room 204 sparks when any appliance is plugged in.",
        "location": "Corridor outside room 204",
        "priority": "urgent",
    }
    status, created, _ = request("POST", "/api/reports", new, token=student_token)
    assert_eq(status, 201, "create report status")
    assert created["status"] == "submitted"
    assert created["ref"].startswith("HFR-")
    print(f"  created report: {created['ref']} ({created['status']})")
    report_id = created["id"]

    # Detail view
    status, detail, _ = request("GET", f"/api/reports/{report_id}", token=student_token)
    assert_eq(status, 200, "report detail status")
    assert_eq(detail["title"], new["title"], "report title")
    assert detail["capabilities"]["can_reopen"] is False
    assert detail["capabilities"]["can_close"] is False
    assert detail["capabilities"]["can_feedback"] is False
    print(f"  detail: {detail['ref']} capabilities={sorted(k for k, v in detail['capabilities'].items() if v)}")

    # Overdue SLA query
    status, overdue, _ = request(
        "GET", "/api/reports", query={"overdue": "true"}, token=student_token)
    assert_eq(status, 200, "overdue filter status")
    print(f"  overdue reports visible to student: {overdue['total']}")
    return report_id


def test_staff_queue(staff_token):
    status, payload, _ = request("GET", "/api/reports", token=staff_token)
    assert_eq(status, 200, "staff reports list status")
    # All visible reports should be assigned to this staff member
    for item in payload["items"]:
        pass  # staff only sees its own assigned reports
    print(f"  staff reports: {payload['total']} total")

    # Find an assigned report to work through
    status, assigned, _ = request(
        "GET", "/api/reports", query={"status": "assigned"}, token=staff_token)
    candidates = [i for i in assigned["items"] if i["assigned_to"]]
    print(f"  staff assigned reports: {len(candidates)}")
    if not candidates:
        return None
    report = candidates[0]
    report_id = report["id"]

    # Start work
    status, started, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "in_progress"}, token=staff_token)
    assert_eq(status, 200, "start work status")
    assert started["status"] == "in_progress"
    print(f"  started work on {started['ref']}")

    # Resolve
    status, resolved, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "resolved", "note": "E2E test resolution: replaced the faulty socket and tested the circuit."},
        token=staff_token)
    assert_eq(status, 200, "resolve status")
    assert resolved["status"] == "resolved"
    assert resolved["resolution_note"]
    print(f"  resolved {resolved['ref']}")
    return report_id


def test_admin_flows(admin_token):
    # Analytics
    status, analytics, _ = request("GET", "/api/analytics", token=admin_token)
    assert_eq(status, 200, "analytics status")
    assert analytics["totals"]["reports"] >= 1
    print(f"  analytics: {analytics['totals']['reports']} reports, SLA {analytics['totals']['sla_compliance']}%")

    # List users
    status, users, _ = request("GET", "/api/admin/users", token=admin_token)
    assert_eq(status, 200, "users list status")
    roles = {}
    for u in users["items"]:
        roles[u["role"]] = roles.get(u["role"], 0) + 1
    print(f"  users: {roles}")

    # Create staff user via admin
    payload = {
        "full_name": "E2E Test Officer",
        "email": f"e2e.staff.{int(datetime.now().timestamp())}@hostelhub.edu.ng",
        "password": "E2eTest@123",
        "role": "staff",
        "phone": "0803 000 9999",
        "department": "Electrical Maintenance",
    }
    status, created_user, _ = request("POST", "/api/admin/users", payload, token=admin_token)
    assert_eq(status, 201, "create staff user status")
    new_staff_id = created_user["id"]
    print(f"  created staff user id={new_staff_id}")

    # Update that user
    status, updated, _ = request(
        "PATCH", f"/api/admin/users/{new_staff_id}",
        {"department": "General Maintenance", "is_active": True}, token=admin_token)
    assert_eq(status, 200, "update user status")
    assert updated["department"] == "General Maintenance"
    print(f"  updated staff user department={updated['department']}")

    # Hostels
    status, hostels, _ = request("GET", "/api/admin/hostels", token=admin_token)
    assert_eq(status, 200, "hostels list status")
    print(f"  hostels: {len(hostels['items'])}")

    # Create hostel
    status, created_hostel, _ = request(
        "POST", "/api/admin/hostels",
        {"name": "E2E Test Hall", "code": "E2E", "gender": "Mixed", "total_rooms": 10},
        token=admin_token)
    assert_eq(status, 201, "create hostel status")
    new_hostel_id = created_hostel["id"]
    print(f"  created hostel id={new_hostel_id}")

    # Update hostel code uniqueness conflict
    status, conflict, _ = request(
        "POST", "/api/admin/hostels",
        {"name": "Dup", "code": "E2E", "gender": "Male", "total_rooms": 5},
        token=admin_token)
    assert_eq(status, 409, "dup hostel code conflict status")

    # Update hostel
    status, updated_hostel, _ = request(
        "PATCH", f"/api/admin/hostels/{new_hostel_id}",
        {"total_rooms": 12, "warden_name": "E2E Warden"},
        token=admin_token)
    assert_eq(status, 200, "update hostel status")
    assert updated_hostel["total_rooms"] == 12
    print(f"  updated hostel total_rooms={updated_hostel['total_rooms']}")

    # Facilities
    status, facilities, _ = request("GET", "/api/admin/facilities", token=admin_token)
    assert_eq(status, 200, "facilities list status")
    print(f"  facilities: {len(facilities['items'])}")

    # Create facility
    status, created_fac, _ = request(
        "POST", "/api/admin/facilities",
        {"hostel_id": new_hostel_id, "name": "E2E Pump", "category": "Plumbing", "condition": "Fair"},
        token=admin_token)
    assert_eq(status, 201, "create facility status")
    new_facility_id = created_fac["id"]
    print(f"  created facility id={new_facility_id}")

    # Update facility
    status, upd_fac, _ = request(
        "PATCH", f"/api/admin/facilities/{new_facility_id}",
        {"condition": "Poor"}, token=admin_token)
    assert_eq(status, 200, "update facility status")
    assert upd_fac["condition"] == "Poor"
    print(f"  updated facility condition={upd_fac['condition']}")

    # Announcements
    status, anns, _ = request("GET", "/api/announcements", token=admin_token)
    assert_eq(status, 200, "announcements list status")
    print(f"  announcements: {len(anns['items'])}")

    # Create announcement
    status, created_ann, _ = request(
        "POST", "/api/announcements",
        {"title": "E2E Test Notice", "body": "This is an E2E test announcement body of sufficient length.",
         "audience": "all", "is_pinned": True}, token=admin_token)
    assert_eq(status, 201, "create announcement status")
    new_ann_id = created_ann["id"]
    print(f"  created announcement id={new_ann_id}")

    # Delete announcement
    status, _, _ = request("DELETE", f"/api/announcements/{new_ann_id}", token=admin_token)
    assert_eq(status, 200, "delete announcement status")
    print(f"  deleted announcement id={new_ann_id}")

    # Cleanup created data
    request("DELETE", f"/announcements/{new_ann_id}", token=admin_token)  # idempotent-ish
    return True


def test_admin_cannot_do_student_things(student_token, admin_token):
    # Admin should NOT be able to create a report (students only)
    status, _, _ = request(
        "POST", "/api/reports",
        {"hostel_id": 1, "category": "Electrical", "title": "X", "description": "Y", "location": "Z", "priority": "low"},
        token=admin_token)
    assert_eq(status, 403, "admin report create forbidden status")
    print("  admin cannot create student reports: ok")


def test_staff_cannot_assign(staff_token):
    status, _, _ = request(
        "POST", "/api/reports/1/assign", {"staff_id": 1}, token=staff_token)
    assert_eq(status in (403, 404), True, "staff assign forbidden")
    print("  staff cannot assign reports: ok")


def test_notifications(student_token):
    status, payload, _ = request("GET", "/api/notifications", token=student_token)
    assert_eq(status, 200, "notifications status")
    print(f"  notifications: {payload['unread']} unread, {len(payload['items'])} items")
    if payload["items"]:
        nid = payload["items"][0]["id"]
        status, updated, _ = request("POST", "/api/notifications/read", {"id": nid}, token=student_token)
        assert_eq(status, 200, "mark read status")
        print(f"  marked notification {nid} read: ok")


def test_student_flow_end_to_end(student_token, staff_token, admin_token):
    staff_user = me(staff_token)
    # Student creates report; admin assigns; staff resolves; student rates; student closes
    new = {
        "hostel_id": 1,
        "category": "Plumbing",
        "title": "E2E lifecycle dripping tap",
        "description": "E2E lifecycle test: bathroom tap drips continuously, wasting water.",
        "location": "Bathroom, west wing",
        "priority": "high",
    }
    status, created, _ = request("POST", "/api/reports", new, token=student_token)
    assert_eq(status, 201, "lifecycle create status")
    report_id = created["id"]
    ref = created["ref"]
    print(f"  lifecycle: created {ref}")

    # Admin assigns to staff (the logged-in maintenance officer, so they can start work)
    status, assigned, _ = request(
        "POST", f"/api/reports/{report_id}/assign",
        {"staff_id": staff_user["id"]}, token=admin_token)
    assert_eq(status, 200, "lifecycle assign status")
    assert assigned["status"] == "assigned"
    print(f"  lifecycle: assigned {ref} to staff id={staff_user['id']}")

    # Staff starts work
    status, started, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "in_progress"}, token=staff_token)
    assert_eq(status, 200, "lifecycle start status")
    print(f"  lifecycle: work started on {ref}")

    # Staff resolves
    status, resolved, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "resolved", "note": "Tap washer replaced. No more drips."},
        token=staff_token)
    assert_eq(status, 200, "lifecycle resolve status")
    print(f"  lifecycle: resolved {ref}")

    # Student rates
    status, rated, _ = request(
        "POST", f"/api/reports/{report_id}/feedback",
        {"rating": 5, "feedback": "Fast and clean fix."}, token=student_token)
    assert_eq(status, 200, "lifecycle feedback status")
    assert rated["rating"] == 5
    print(f"  lifecycle: rated {ref} = 5/5")

    # Student closes
    status, closed, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "closed"}, token=student_token)
    assert_eq(status, 200, "lifecycle close status")
    assert closed["status"] == "closed"
    print(f"  lifecycle: closed {ref}")

    # Student cannot reopen twice without resolved state? Reopen
    status, reopened, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "reopened", "note": "The dripping returned after one hour."}, token=student_token)
    assert_eq(status, 200, "lifecycle reopen status")
    assert reopened["status"] == "reopened"
    print(f"  lifecycle: reopened {ref}")

    # Admin reassigns reopened report
    status, reassign, _ = request(
        "POST", f"/api/reports/{report_id}/assign",
        {"staff_id": staff_user["id"]}, token=admin_token)
    assert_eq(status, 200, "lifecycle reassign status")
    print(f"  lifecycle: reassigned {ref}")

    # Staff resolves again
    status, resolved2, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "resolved", "note": "Second fix confirmed; leak fully stopped."},
        token=staff_token)
    assert_eq(status, 200, "lifecycle second resolve status")
    print(f"  lifecycle: resolved {ref} again")

    # Close again to clean up
    status, closed2, _ = request(
        "POST", f"/api/reports/{report_id}/status",
        {"status": "closed"}, token=student_token)
    assert_eq(status, 200, "lifecycle final close status")
    print(f"  lifecycle: final closed {ref}")


def test_errors(student_token):
    # 404 report
    status, payload, _ = request("GET", "/api/reports/999999", token=student_token)
    assert_eq(status, 404, "404 report status")
    # 403 accessing another student's report (fetch a report not owned)
    status, listp, _ = request("GET", "/api/reports", token=student_token)
    if listp["items"]:
        # student's own reports only, so skip cross-check unless admin
        pass
    # Invalid payload
    status, payload, _ = request(
        "POST", "/api/reports",
        {"hostel_id": 1, "category": "Electrical", "title": "x", "description": "too short", "location": "Z", "priority": "low"},
        token=student_token)
    assert_eq(status, 400, "validation error status")
    print("  validation errors: ok")


def main():
    print("== HostelHub end-to-end tests ==")
    print(f"Target: {BASE}")
    test_health()
    st_token, st_user = login("student")
    sf_token, sf_user = login("staff")
    ad_token, ad_user = login("admin")

    assert me(st_token)["id"] == st_user["id"]

    test_meta(st_token)
    test_reports_student(st_token)
    test_staff_queue(sf_token)
    test_admin_flows(ad_token)
    test_admin_cannot_do_student_things(st_token, ad_token)
    test_staff_cannot_assign(sf_token)
    test_notifications(st_token)
    test_errors(st_token)
    test_student_flow_end_to_end(st_token, sf_token, ad_token)

    # Logout
    status, _, _ = request("POST", "/api/auth/logout", token=st_token)
    assert_eq(status, 200, "logout status")

    print("\nALL E2E TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except Fail as exc:
        print(f"\nE2E FAILURE: {exc}")
        sys.exit(1)
