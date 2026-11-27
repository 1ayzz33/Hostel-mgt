"""Create a realistic demo dataset for HostelHub.

Run `python seed.py` for an idempotent seed or `python seed.py --reset` to
rebuild the database from scratch.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import timedelta

from .config import DB_PATH
from .db import connect, init_db
from .security import hash_password
from .utils import iso, utc_now

DEMO_ACCOUNTS = [
    ("admin@hostelhub.edu.ng", "Admin@123", "admin"),
    ("student@hostelhub.edu.ng", "Student@123", "student"),
    ("grace.okafor@hostelhub.edu.ng", "Staff@123", "staff"),
]

HOSTELS = [
    ("New Block A", "NBA", "Female", "North Campus, beside Faculty of Science", "Mrs. Rebecca Atabo", "0803 111 2233", 120),
    ("Unity Hall", "UNH", "Male", "Central Campus, behind the Students' Union", "Mr. Ibrahim Sule", "0806 222 3344", 96),
    ("Scholars' Lodge", "SCL", "Mixed", "South Campus, along University Road", "Dr. Helen Oche", "0812 333 4455", 80),
    ("Heritage Court", "HRC", "Female", "East Campus, near the Health Centre", "Mrs. Phoebe Gyang", "0809 444 5566", 64),
]

USERS = [
    # full name, email, password, role, student id, phone, hostel code, room, department
    ("Aisha Bello", "admin@hostelhub.edu.ng", "Admin@123", "admin", None, "0803 000 1001", None, "", "Student Affairs"),
    ("Sarah Adamu", "student@hostelhub.edu.ng", "Student@123", "student", "NSUK/CSC/21/041", "0806 700 1001", "NBA", "204", "Computer Science"),
    ("David Okon", "david.okon@hostelhub.edu.ng", "Student@123", "student", "NSUK/ENG/21/018", "0806 700 1002", "UNH", "112", "Mechanical Engineering"),
    ("Halima Sule", "halima.sule@hostelhub.edu.ng", "Student@123", "student", "NSUK/SCI/22/076", "0806 700 1003", "SCL", "018", "Microbiology"),
    ("Chinedu Eze", "chinedu.eze@hostelhub.edu.ng", "Student@123", "student", "NSUK/ACC/21/033", "0806 700 1004", "UNH", "208", "Accounting"),
    ("Fatima Yusuf", "fatima.yusuf@hostelhub.edu.ng", "Student@123", "student", "NSUK/LAW/22/009", "0806 700 1005", "HRC", "106", "Law"),
    ("Peter James", "peter.james@hostelhub.edu.ng", "Student@123", "student", "NSUK/CSC/22/102", "0806 700 1006", "SCL", "022", "Computer Science"),
    ("Grace Okafor", "grace.okafor@hostelhub.edu.ng", "Staff@123", "staff", None, "0803 800 2001", None, "", "Electrical & General Maintenance"),
    ("Friday Audu", "friday.audu@hostelhub.edu.ng", "Staff@123", "staff", None, "0803 800 2002", None, "", "Plumbing & Sanitation"),
    ("Musa Danjuma", "musa.danjuma@hostelhub.edu.ng", "Staff@123", "staff", None, "0803 800 2003", None, "", "ICT & Network Support"),
    ("Esther Nwosu", "esther.nwosu@hostelhub.edu.ng", "Staff@123", "staff", None, "0803 800 2004", None, "", "Housekeeping"),
]

FACILITIES = [
    ("NBA", "Main corridor lights", "Electrical", "Ground floor corridor", "Good"),
    ("NBA", "Bathroom water heater", "Plumbing", "Second floor, west wing", "Fair"),
    ("NBA", "Study room reading tables", "Furniture", "Block A study room", "Fair"),
    ("UNH", "Common room television", "Electrical", "Common room", "Good"),
    ("UNH", "Kitchen sink", "Plumbing", "Kitchenette", "Poor"),
    ("UNH", "Hostel Wi-Fi access point", "Internet / ICT", "First floor", "Fair"),
    ("SCL", "Laundry washing machines", "Other", "Laundry room", "Fair"),
    ("SCL", "Ceiling fans", "HVAC / Ventilation", "Rooms 010–030", "Good"),
    ("HRC", "Main entrance door lock", "Security", "Main entrance", "Fair"),
    ("HRC", "Refuse collection point", "Sanitation", "Rear compound", "Poor"),
]

REPORTS = [
    {
        "student": "student@hostelhub.edu.ng",
        "hostel": "NBA",
        "category": "Plumbing",
        "title": "Bathroom pipe leaking into the corridor",
        "description": "The cold-water pipe under the second-floor bathroom sink has been dripping since Monday. Water is now spreading across the corridor and the tiles are slippery.",
        "location": "Second floor bathroom, west wing",
        "priority": "high",
        "status": "resolved",
        "staff": "friday.audu@hostelhub.edu.ng",
        "days_ago": 34,
        "resolved_days_ago": 33,
        "rating": 5,
        "feedback": "The plumber came the next morning and replaced the joint. Very fast response.",
    },
    {
        "student": "student@hostelhub.edu.ng",
        "hostel": "NBA",
        "category": "Electrical",
        "title": "Two sockets sparking near my reading desk",
        "description": "The wall sockets beside the reading desk spark whenever I plug in my laptop charger. I have stopped using them because it feels unsafe.",
        "location": "Room 204, reading desk",
        "priority": "urgent",
        "status": "in_progress",
        "staff": "grace.okafor@hostelhub.edu.ng",
        "days_ago": 1,
    },
    {
        "student": "david.okon@hostelhub.edu.ng",
        "hostel": "UNH",
        "category": "Furniture",
        "title": "Broken reading table in the common study room",
        "description": "One of the long reading tables has a cracked top and a loose leg. It wobbles badly and students have stopped using that side of the room.",
        "location": "Unity Hall study room",
        "priority": "medium",
        "status": "submitted",
        "days_ago": 2,
    },
    {
        "student": "halima.sule@hostelhub.edu.ng",
        "hostel": "SCL",
        "category": "Internet / ICT",
        "title": "Wi-Fi keeps disconnecting on the first floor",
        "description": "The hostel Wi-Fi drops every few minutes on the first floor. Online lectures and assignment submissions are being affected, especially in the evening.",
        "location": "First floor, rooms 014–024",
        "priority": "high",
        "status": "assigned",
        "staff": "musa.danjuma@hostelhub.edu.ng",
        "days_ago": 3,
    },
    {
        "student": "chinedu.eze@hostelhub.edu.ng",
        "hostel": "UNH",
        "category": "Plumbing",
        "title": "Kitchen sink is blocked and overflowing",
        "description": "The kitchen sink drains very slowly and now overflows whenever more than two people are washing plates. The floor stays wet for hours.",
        "location": "Unity Hall kitchenette",
        "priority": "high",
        "status": "resolved",
        "staff": "friday.audu@hostelhub.edu.ng",
        "days_ago": 17,
        "resolved_days_ago": 16,
        "rating": 4,
        "feedback": "Drain was cleared properly, although it took a full day.",
    },
    {
        "student": "fatima.yusuf@hostelhub.edu.ng",
        "hostel": "HRC",
        "category": "Security",
        "title": "Main entrance door lock is loose",
        "description": "The main entrance lock no longer catches properly and the door can be pushed open at night. This is a security concern for everyone in the hostel.",
        "location": "Heritage Court main entrance",
        "priority": "urgent",
        "status": "assigned",
        "staff": "friday.audu@hostelhub.edu.ng",
        "days_ago": 5,
    },
    {
        "student": "peter.james@hostelhub.edu.ng",
        "hostel": "SCL",
        "category": "Plumbing",
        "title": "Water heater stopped working after power surge",
        "description": "The water heater in the shared bathroom stopped heating after the power surge last week. The indicator light is off and the unit makes a clicking sound.",
        "location": "Second floor shared bathroom",
        "priority": "medium",
        "status": "reopened",
        "staff": "grace.okafor@hostelhub.edu.ng",
        "days_ago": 21,
        "resolved_days_ago": 14,
        "reopened_days_ago": 2,
        "reopen_note": "The heater worked for two days and has stopped again. The same clicking sound is back.",
    },
    {
        "student": "david.okon@hostelhub.edu.ng",
        "hostel": "UNH",
        "category": "Sanitation",
        "title": "Refuse bins have not been emptied for a week",
        "description": "The bins at the rear of Unity Hall are full and rubbish is spilling into the compound. There is a strong smell and flies are gathering around the area.",
        "location": "Rear compound, beside the laundry line",
        "priority": "medium",
        "status": "closed",
        "staff": "esther.nwosu@hostelhub.edu.ng",
        "days_ago": 47,
        "resolved_days_ago": 46,
        "closed_days_ago": 44,
        "rating": 5,
        "feedback": "Bins were emptied and the area was washed. Thank you.",
    },
    {
        "student": "halima.sule@hostelhub.edu.ng",
        "hostel": "SCL",
        "category": "HVAC / Ventilation",
        "title": "Ceiling fan in room 018 is making a loud noise",
        "description": "The ceiling fan vibrates loudly at speed two and three. It is difficult to sleep, and I am worried the mounting may be loose.",
        "location": "Room 018",
        "priority": "medium",
        "status": "in_progress",
        "staff": "grace.okafor@hostelhub.edu.ng",
        "days_ago": 7,
    },
    {
        "student": "chinedu.eze@hostelhub.edu.ng",
        "hostel": "UNH",
        "category": "Electrical",
        "title": "Common room television has no picture",
        "description": "The television in the common room powers on but there is no picture. Only sound comes through, and the screen stays black.",
        "location": "Unity Hall common room",
        "priority": "low",
        "status": "resolved",
        "staff": "grace.okafor@hostelhub.edu.ng",
        "days_ago": 61,
        "resolved_days_ago": 58,
        "rating": 4,
    },
    {
        "student": "fatima.yusuf@hostelhub.edu.ng",
        "hostel": "HRC",
        "category": "Furniture",
        "title": "Wardrobe door fell off its hinges",
        "description": "The left door of my wardrobe came off its hinges and is now leaning against the wall. I cannot secure my belongings properly.",
        "location": "Room 106",
        "priority": "medium",
        "status": "resolved",
        "staff": "grace.okafor@hostelhub.edu.ng",
        "days_ago": 94,
        "resolved_days_ago": 92,
        "rating": 5,
        "feedback": "Fixed the same day it was assigned.",
    },
    {
        "student": "peter.james@hostelhub.edu.ng",
        "hostel": "SCL",
        "category": "Sanitation",
        "title": "Cockroaches in the laundry room",
        "description": "There are cockroaches around the laundry sinks and behind the washing machines. I saw several after dark and would like pest control to visit.",
        "location": "Laundry room",
        "priority": "low",
        "status": "submitted",
        "days_ago": 9,
    },
    {
        "student": "student@hostelhub.edu.ng",
        "hostel": "NBA",
        "category": "Internet / ICT",
        "title": "Wi-Fi password not working after router reset",
        "description": "The New Block A Wi-Fi asks for a password but rejects the one on the notice board. Other students on the second floor are having the same problem.",
        "location": "Second floor, Block A",
        "priority": "medium",
        "status": "resolved",
        "staff": "musa.danjuma@hostelhub.edu.ng",
        "days_ago": 128,
        "resolved_days_ago": 127,
        "rating": 3,
        "feedback": "It was fixed, but I had to call the ICT office twice before anyone came.",
    },
    {
        "student": "david.okon@hostelhub.edu.ng",
        "hostel": "UNH",
        "category": "Electrical",
        "title": "Corridor light stays on all day",
        "description": "The corridor light outside room 112 never goes off. It is wasting power and shines into the rooms at night.",
        "location": "First floor corridor, Unity Hall",
        "priority": "low",
        "status": "closed",
        "staff": "grace.okafor@hostelhub.edu.ng",
        "days_ago": 152,
        "resolved_days_ago": 150,
        "closed_days_ago": 149,
        "rating": 5,
    },
    {
        "student": "halima.sule@hostelhub.edu.ng",
        "hostel": "SCL",
        "category": "Other",
        "title": "Laundry machine door will not open",
        "description": "The middle washing machine finished its cycle but the door is stuck. My clothes have been trapped inside since yesterday evening.",
        "location": "Laundry room",
        "priority": "high",
        "status": "submitted",
        "days_ago": 0,
    },
]


def _password_cache() -> dict[str, str]:
    cache: dict[str, str] = {}
    for _, password, _ in DEMO_ACCOUNTS:
        cache.setdefault(password, hash_password(password))
    return cache


def seed_database(conn: sqlite3.Connection, reset: bool = False) -> dict:
    if reset:
        for table in (
            "sessions", "notifications", "report_updates", "reports", "announcements",
            "facilities", "users", "hostels",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")
        conn.commit()

    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing:
        return {"seeded": False, "reason": "Database already contains users."}

    now = utc_now()
    passwords = _password_cache()

    hostel_ids: dict[str, int] = {}
    for name, code, gender, address, warden, phone, rooms in HOSTELS:
        cur = conn.execute(
            """INSERT INTO hostels
               (name, code, gender, address, warden_name, warden_phone, total_rooms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, code, gender, address, warden, phone, rooms, iso(now - timedelta(days=220))),
        )
        hostel_ids[code] = cur.lastrowid

    user_ids: dict[str, int] = {}
    for full_name, email, password, role, student_id, phone, hostel_code, room, department in USERS:
        cur = conn.execute(
            """INSERT INTO users
               (full_name, email, password_hash, role, student_id, phone, hostel_id,
                room_number, department, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                full_name,
                email,
                passwords[password],
                role,
                student_id,
                phone,
                hostel_ids.get(hostel_code),
                room,
                department,
                iso(now - timedelta(days=210)),
                iso(now - timedelta(days=210)),
            ),
        )
        user_ids[email] = cur.lastrowid

    facility_ids: dict[tuple[str, str], int] = {}
    facility_by_category: dict[tuple[str, str], int] = {}
    for hostel_code, name, category, location, condition in FACILITIES:
        cur = conn.execute(
            """INSERT INTO facilities (hostel_id, name, category, location, condition, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                hostel_ids[hostel_code],
                name,
                category,
                location,
                condition,
                iso(now - timedelta(days=180)),
            ),
        )
        facility_ids[(hostel_code, name)] = cur.lastrowid
        facility_by_category.setdefault((hostel_code, category), cur.lastrowid)

    report_refs: dict[int, str] = {}
    for index, report in enumerate(REPORTS, start=1):
        created = now - timedelta(days=report["days_ago"], hours=3)
        resolved = (
            now - timedelta(days=report["resolved_days_ago"], hours=2)
            if report.get("resolved_days_ago") is not None
            else None
        )
        reopened = (
            now - timedelta(days=report["reopened_days_ago"], hours=1)
            if report.get("reopened_days_ago") is not None
            else None
        )
        closed = (
            now - timedelta(days=report["closed_days_ago"], hours=1)
            if report.get("closed_days_ago") is not None
            else None
        )
        student_id = user_ids[report["student"]]
        staff_id = user_ids.get(report.get("staff"))
        ref = f"HFR-{created.year}-{index:04d}"
        report_refs[index] = ref
        effective_resolved = None if reopened else resolved
        cur = conn.execute(
            """INSERT INTO reports
               (ref, student_id, hostel_id, facility_id, category, title, description,
                location, priority, status, assigned_to, created_at, updated_at,
                resolved_at, resolution_note, rating, feedback)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ref,
                student_id,
                hostel_ids[report["hostel"]],
                facility_by_category.get((report["hostel"], report["category"])),
                report["category"],
                report["title"],
                report["description"],
                report["location"],
                report["priority"],
                report["status"],
                staff_id,
                iso(created),
                iso(closed or reopened or resolved or created),
                iso(effective_resolved) if effective_resolved else None,
                (
                    "Fault traced and repaired. The area was checked and cleaned after the work."
                    if effective_resolved else None
                ),
                report.get("rating") if effective_resolved else None,
                report.get("feedback") if effective_resolved else None,
            ),
        )
        report_id = cur.lastrowid
        conn.execute(
            """INSERT INTO report_updates
               (report_id, user_id, action, note, from_status, to_status, is_internal, created_at)
               VALUES (?, ?, 'created', 'Report submitted and queued for review.', NULL,
                       'submitted', 0, ?)""",
            (report_id, student_id, iso(created)),
        )
        timeline = created
        if staff_id:
            timeline = created + timedelta(hours=6)
            conn.execute(
                """INSERT INTO report_updates
                   (report_id, user_id, action, note, from_status, to_status, is_internal, created_at)
                   VALUES (?, ?, 'assigned', ?, 'submitted', 'assigned', 0, ?)""",
                (
                    report_id,
                    user_ids["admin@hostelhub.edu.ng"],
                    f"Assigned to {report['staff'].split('@')[0].replace('.', ' ').title()}.",
                    iso(timeline),
                ),
            )
        if report["status"] in ("in_progress", "resolved", "closed", "reopened"):
            timeline = created + timedelta(hours=20)
            conn.execute(
                """INSERT INTO report_updates
                   (report_id, user_id, action, note, from_status, to_status, is_internal, created_at)
                   VALUES (?, ?, 'in_progress', 'Maintenance team has started work on site.',
                           'assigned', 'in_progress', 0, ?)""",
                (report_id, staff_id, iso(timeline)),
            )
        if resolved:
            conn.execute(
                """INSERT INTO report_updates
                   (report_id, user_id, action, note, from_status, to_status, is_internal, created_at)
                   VALUES (?, ?, 'resolved', ?, 'in_progress', 'resolved', 0, ?)""",
                (
                    report_id,
                    staff_id,
                    "Fault traced and repaired. The area was checked and cleaned after the work.",
                    iso(resolved),
                ),
            )
        if closed:
            conn.execute(
                """INSERT INTO report_updates
                   (report_id, user_id, action, note, from_status, to_status, is_internal, created_at)
                   VALUES (?, ?, 'closed', 'Student confirmed the fix and closed the report.',
                           'resolved', 'closed', 0, ?)""",
                (report_id, student_id, iso(closed)),
            )
        if reopened:
            conn.execute(
                """INSERT INTO report_updates
                   (report_id, user_id, action, note, from_status, to_status, is_internal, created_at)
                   VALUES (?, ?, 'reopened', ?, 'resolved', 'reopened', 0, ?)""",
                (report_id, student_id, report.get("reopen_note", ""), iso(reopened)),
            )

    # A few purposeful notifications so the bell is useful on first login.
    notifications = [
        (
            user_ids["student@hostelhub.edu.ng"],
            "Report resolved",
            f"{report_refs[1]} has been marked resolved. Please rate the service.",
            1,
            33,
        ),
        (
            user_ids["student@hostelhub.edu.ng"],
            "Report assigned",
            f"{report_refs[2]} has been assigned to Grace Okafor.",
            2,
            1,
        ),
        (
            user_ids["grace.okafor@hostelhub.edu.ng"],
            "Urgent report assigned",
            f"{report_refs[2]} – Two sockets sparking near my reading desk is now in your queue.",
            2,
            1,
        ),
        (
            user_ids["admin@hostelhub.edu.ng"],
            "Report reopened",
            f"{report_refs[7]} was reopened by the student and needs reassignment.",
            7,
            2,
        ),
    ]
    for user_id, title, message, report_id, days in notifications:
        conn.execute(
            """INSERT INTO notifications
               (user_id, report_id, title, message, is_read, created_at)
               VALUES (?, ?, ?, ?, 0, ?)""",
            (user_id, report_id, title, message, iso(now - timedelta(days=days))),
        )

    announcements = [
        (
            "Water supply maintenance this Saturday",
            "There will be a planned water-supply interruption in New Block A and Heritage Court on Saturday from 9:00 am to 2:00 pm. Please store enough water for the morning. The maintenance team will restore supply as soon as the overhead tanks have been cleaned.",
            "all",
            1,
        ),
        (
            "New reporting turnaround times",
            "Facility reports are now triaged by priority: urgent issues within 6 hours, high within 24 hours, medium within 48 hours and low within 72 hours. Please include a clear location and a photo where possible so the maintenance team can respond faster.",
            "students",
            0,
        ),
        (
            "Weekly maintenance stand-up",
            "All maintenance staff should meet at the Works Department by 8:30 am every Monday for queue review and assignment handover. Bring updates on any report that has passed its SLA deadline.",
            "staff",
            0,
        ),
    ]
    for title, body, audience, pinned in announcements:
        conn.execute(
            """INSERT INTO announcements
               (title, body, audience, is_pinned, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                title,
                body,
                audience,
                pinned,
                user_ids["admin@hostelhub.edu.ng"],
                iso(now - timedelta(days=2)),
            ),
        )

    conn.commit()
    return {
        "seeded": True,
        "hostels": len(HOSTELS),
        "users": len(USERS),
        "reports": len(REPORTS),
        "accounts": DEMO_ACCOUNTS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the HostelHub demo database.")
    parser.add_argument("--reset", action="store_true", help="Delete existing data first.")
    args = parser.parse_args()
    init_db(DB_PATH)
    with connect(DB_PATH) as conn:
        result = seed_database(conn, reset=args.reset)
    print(f"Database: {DB_PATH}")
    if result["seeded"]:
        print(
            f"Seeded {result['hostels']} hostels, {result['users']} users and "
            f"{result['reports']} reports."
        )
        print("\nDemo accounts")
        print("  Student : student@hostelhub.edu.ng / Student@123")
        print("  Staff   : grace.okafor@hostelhub.edu.ng / Staff@123")
        print("  Admin   : admin@hostelhub.edu.ng / Admin@123")
    else:
        print(result["reason"])


if __name__ == "__main__":
    main()
