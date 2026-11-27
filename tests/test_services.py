"""Unit tests for the HostelHub services layer.

Run from the project root:

    python -m unittest tests.test_services -v
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# Point the app at a throwaway database before importing the application modules.
os.environ["HOSTELHUB_DB"] = str(
    Path(tempfile.gettempdir()) / f"hostelhub_tests_{os.getpid()}.db"
)

from hostelhub.config import DB_PATH  # noqa: E402
from hostelhub.db import database, init_db  # noqa: E402
from hostelhub import services  # noqa: E402
from hostelhub.errors import ApiError  # noqa: E402


def clean_db(conn):
    """Remove every row so tests are isolated, keeping the schema."""
    for table in (
        "sessions", "notifications", "report_updates", "reports",
        "announcements", "facilities", "users", "hostels",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()


class SecurityTests(unittest.TestCase):
    def test_password_hash_verify(self):
        encoded = services.hash_password("SuperSecret123")
        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))
        self.assertTrue(services.verify_password("SuperSecret123", encoded))
        self.assertFalse(services.verify_password("WrongSecret123", encoded))
        self.assertFalse(services.verify_password("SuperSecret123", "garbage"))

    def test_email_normalisation(self):
        self.assertEqual(
            services.normalise_email("  User@Example.COM "), "user@example.com"
        )
        self.assertTrue(services.valid_email("a@b.co"))
        self.assertFalse(services.valid_email("not-an-email"))


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        init_db(DB_PATH)
        with database() as conn:
            clean_db(conn)

    def test_schema_tables_exist(self):
        with database() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        for required in (
            "users", "hostels", "facilities", "reports", "report_updates",
            "notifications", "announcements", "sessions",
        ):
            self.assertIn(required, tables)


class AuthTests(unittest.TestCase):
    def setUp(self):
        init_db(DB_PATH)
        with database() as conn:
            clean_db(conn)
            self.admin = services.create_user(
                conn,
                {
                    "full_name": "Admin User",
                    "email": "admin@hostelhub.edu.ng",
                    "password": "Admin@1234",
                    "role": "admin",
                },
                allow_roles=True,
            )

    def test_student_registration_defaults_to_student(self):
        with database() as conn:
            hostel = services.create_hostel(
                conn, {"name": "Test Hall", "code": "TH", "gender": "Mixed", "total_rooms": 10}
            )
            user = services.create_user(
                conn,
                {
                    "full_name": "Sarah Adamu",
                    "email": "sarah@hostelhub.edu.ng",
                    "password": "Student@123",
                    "student_id": "NSUK/CSC/21/041",
                    "hostel_id": hostel["id"],
                },
            )
        self.assertEqual(user["role"], "student")
        self.assertEqual(user["student_id"], "NSUK/CSC/21/041")
        self.assertIsNone(user.get("password_hash"))

    def test_duplicate_email_rejected(self):
        with database() as conn:
            with self.assertRaises(ApiError) as ctx:
                services.create_user(
                    conn,
                    {
                        "full_name": "Dup",
                        "email": "ADMIN@HOSTELHUB.EDU.NG",
                        "password": "Admin@1234",
                        "role": "admin",
                    },
                    allow_roles=True,
                )
        self.assertEqual(ctx.exception.status, 409)

    def test_student_requires_matric_number(self):
        with database() as conn:
            with self.assertRaises(ApiError) as ctx:
                services.create_user(
                    conn,
                    {
                        "full_name": "No Matric",
                        "email": "nomatric@hostelhub.edu.ng",
                        "password": "Student@123",
                        "role": "student",
                    },
                    allow_roles=True,
                )
        self.assertEqual(ctx.exception.status, 400)

    def test_password_too_short_rejected(self):
        with database() as conn:
            with self.assertRaises(ApiError) as ctx:
                services.create_user(
                    conn,
                    {
                        "full_name": "Weak User",
                        "email": "weak@hostelhub.edu.ng",
                        "password": "short",
                        "role": "student",
                        "student_id": "NSUK/1/1",
                    },
                    allow_roles=True,
                )
        self.assertEqual(ctx.exception.status, 400)

    def test_authenticate(self):
        with database() as conn:
            user = services.authenticate(conn, "admin@hostelhub.edu.ng", "Admin@1234")
            self.assertEqual(user["role"], "admin")
            with self.assertRaises(ApiError) as ctx:
                services.authenticate(conn, "admin@hostelhub.edu.ng", "wrong")
            self.assertEqual(ctx.exception.status, 401)
            # Deactivate a *different* admin (self-deactivation is blocked).
            other_admin = services.create_user(
                conn,
                {
                    "full_name": "Second Admin",
                    "email": "admin2@hostelhub.edu.ng",
                    "password": "Admin@1234",
                    "role": "admin",
                },
                allow_roles=True,
            )
            services.admin_update_user(
                conn, self.admin, other_admin["id"], {"is_active": False}
            )
            with self.assertRaises(ApiError) as ctx:
                services.authenticate(conn, "admin2@hostelhub.edu.ng", "Admin@1234")
            self.assertEqual(ctx.exception.status, 403)

    def test_session_create_and_resolve(self):
        with database() as conn:
            token = services.create_session(conn, self.admin["id"])
            user = services.resolve_session(conn, token)
            self.assertEqual(user["id"], self.admin["id"])
            self.assertIsNone(services.resolve_session(conn, "bogus-token"))
            services.revoke_session(conn, token)
            self.assertIsNone(services.resolve_session(conn, token))

    def test_admin_cannot_demote_self_only_admin(self):
        with database() as conn:
            with self.assertRaises(ApiError) as ctx:
                services.admin_update_user(
                    conn, self.admin, self.admin["id"], {"role": "staff"}
                )
            self.assertEqual(ctx.exception.status, 409)


class ReportTests(unittest.TestCase):
    def setUp(self):
        init_db(DB_PATH)
        with database() as conn:
            clean_db(conn)
            self.admin = services.create_user(
                conn,
                {"full_name": "Admin", "email": "a@h.edu.ng", "password": "Admin@1234", "role": "admin"},
                allow_roles=True,
            )
            self.staff = services.create_user(
                conn,
                {"full_name": "Staff", "email": "s@h.edu.ng", "password": "Staff@1234", "role": "staff"},
                allow_roles=True,
            )
            self.student = services.create_user(
                conn,
                {"full_name": "Student User", "email": "st@h.edu.ng", "password": "Student@1234", "role": "student",
                 "student_id": "NSUK/1/1"},
                allow_roles=True,
            )
            self.hostel = services.create_hostel(
                conn, {"name": "Test Hall", "code": "TH", "gender": "Mixed", "total_rooms": 10}
            )
            self.facility = services.create_facility(
                conn,
                {"hostel_id": self.hostel["id"], "name": "Tap", "category": "Plumbing", "condition": "Good"},
            )

    def tearDown(self):
        pass

    def test_student_can_create_report(self):
        with database() as conn:
            report = services.create_report(
                conn, self.student,
                {
                    "hostel_id": self.hostel["id"],
                    "facility_id": self.facility["id"],
                    "category": "Plumbing",
                    "title": "Dripping tap in bathroom",
                    "description": "The bathroom tap drips continuously and wastes water.",
                    "location": "Second floor bathroom",
                    "priority": "high",
                },
            )
        self.assertEqual(report["status"], "submitted")
        self.assertTrue(report["ref"].startswith("HFR-"))
        self.assertEqual(report["category"], "Plumbing")

    def test_staff_cannot_create_report(self):
        with database() as conn:
            with self.assertRaises(ApiError) as ctx:
                services.create_report(
                    conn, self.staff,
                    {
                        "hostel_id": self.hostel["id"],
                        "category": "Plumbing",
                        "title": "X",
                        "description": "Y",
                        "location": "Z",
                        "priority": "low",
                    },
                )
        self.assertEqual(ctx.exception.status, 403)

    def test_report_lifecycle(self):
        with database() as conn:
            report = services.create_report(
                conn, self.student,
                {
                    "hostel_id": self.hostel["id"],
                    "category": "Electrical",
                    "title": "Sparking socket",
                    "description": "The socket near my desk sparks when I plug in a charger.",
                    "location": "Room 101",
                    "priority": "urgent",
                },
            )
            report_id = report["id"]

            assigned = services.assign_report(
                conn, self.admin, report_id, self.staff["id"], "Please attend urgently."
            )
            self.assertEqual(assigned["status"], "assigned")
            self.assertEqual(assigned["assigned_to"], self.staff["id"])

            started = services.change_status(
                conn, self.staff, report_id, "in_progress",
            )
            self.assertEqual(started["status"], "in_progress")

            resolved = services.change_status(
                conn, self.staff, report_id, "resolved",
                "Socket replaced and circuit tested.",
            )
            self.assertEqual(resolved["status"], "resolved")
            self.assertIsNotNone(resolved["resolution_note"])

            rated = services.submit_feedback(
                conn, self.student, report_id, 5, "Excellent service."
            )
            self.assertEqual(rated["rating"], 5)

            closed = services.change_status(conn, self.student, report_id, "closed")
            self.assertEqual(closed["status"], "closed")

            reopened = services.change_status(
                conn, self.student, report_id, "reopened",
                "The sparking came back after one hour.",
            )
            self.assertEqual(reopened["status"], "reopened")

    def test_student_cannot_close_unresolved_report(self):
        with database() as conn:
            report = services.create_report(
                conn, self.student,
                {
                    "hostel_id": self.hostel["id"],
                    "category": "Electrical",
                    "title": "Unresolved report test",
                    "description": "This is an unresolved report used for the close permission check.",
                    "location": "Bathroom, west wing",
                    "priority": "low",
                },
            )
            with self.assertRaises(ApiError) as ctx:
                services.change_status(conn, self.student, report["id"], "closed")
            self.assertEqual(ctx.exception.status, 403)

    def test_unassigned_staff_cannot_resolve(self):
        with database() as conn:
            other_staff = services.create_user(
                conn,
                {"full_name": "Other", "email": "o@h.edu.ng", "password": "Staff@1234", "role": "staff"},
                allow_roles=True,
            )
            report = services.create_report(
                conn, self.student,
                {
                    "hostel_id": self.hostel["id"],
                    "category": "Electrical",
                    "title": "Unassigned staff resolve test",
                    "description": "This report is assigned to another staff member.",
                    "location": "Room 101",
                    "priority": "low",
                },
            )
            services.assign_report(conn, self.admin, report["id"], self.staff["id"], "n")
            with self.assertRaises(ApiError) as ctx:
                services.change_status(
                    conn, other_staff, report["id"], "resolved", "Fixed."
                )
            self.assertEqual(ctx.exception.status, 403)

    def test_student_sees_only_own_reports(self):
        with database() as conn:
            services.create_report(
                conn, self.student,
                {"hostel_id": self.hostel["id"], "category": "Electrical", "title": "Report one",
                 "description": "First report used to verify student-scoped listing.", "location": "Room 101",
                 "priority": "low"},
            )
            other = services.create_user(
                conn,
                {"full_name": "Other User", "email": "o2@h.edu.ng", "password": "Student@1234",
                 "role": "student", "student_id": "NSUK/2/2"},
                allow_roles=True,
            )
            services.create_report(
                conn, other,
                {"hostel_id": self.hostel["id"], "category": "Plumbing", "title": "Report two",
                 "description": "Second report used to verify student-scoped listing.", "location": "Room 202",
                 "priority": "low"},
            )
            mine = services.list_reports(conn, self.student, {})
            theirs = services.list_reports(conn, other, {})
        self.assertEqual(len(mine["items"]), 1)
        self.assertEqual(len(theirs["items"]), 1)


class AdminTests(unittest.TestCase):
    def setUp(self):
        init_db(DB_PATH)
        with database() as conn:
            clean_db(conn)
            self.admin = services.create_user(
                conn,
                {"full_name": "Admin", "email": "a@h.edu.ng", "password": "Admin@1234", "role": "admin"},
                allow_roles=True,
            )

    def tearDown(self):
        pass

    def test_create_and_update_hostel(self):
        with database() as conn:
            hostel = services.create_hostel(
                conn, {"name": "Unity Hall", "code": "UNH", "gender": "Male", "total_rooms": 50}
            )
            self.assertEqual(hostel["code"], "UNH")
            updated = services.update_hostel(
                conn, hostel["id"], {"total_rooms": 52, "warden_name": "Warden One"}
            )
            self.assertEqual(updated["total_rooms"], 52)
            self.assertEqual(updated["warden_name"], "Warden One")

    def test_duplicate_hostel_code_rejected(self):
        with database() as conn:
            services.create_hostel(
                conn, {"name": "One", "code": "DUP", "gender": "Mixed", "total_rooms": 5}
            )
            with self.assertRaises(ApiError) as ctx:
                services.create_hostel(
                    conn, {"name": "Two", "code": "dup", "gender": "Mixed", "total_rooms": 5}
                )
        self.assertEqual(ctx.exception.status, 409)

    def test_create_and_update_facility(self):
        with database() as conn:
            hostel = services.create_hostel(
                conn, {"name": "Hall", "code": "HL", "gender": "Mixed", "total_rooms": 5}
            )
            facility = services.create_facility(
                conn,
                {"hostel_id": hostel["id"], "name": "Pump", "category": "Plumbing", "condition": "Good"},
            )
            updated = services.update_facility(
                conn, facility["id"], {"condition": "Under repair"}
            )
            self.assertEqual(updated["condition"], "Under repair")

    def test_admin_cannot_delete_last_admin(self):
        with database() as conn:
            with self.assertRaises(ApiError) as ctx:
                services.admin_update_user(
                    conn, self.admin, self.admin["id"], {"is_active": False}
                )
            self.assertEqual(ctx.exception.status, 409)

    def test_analytics_without_admin_rejected(self):
        with database() as conn:
            student = services.create_user(
                conn,
                {"full_name": "Student User", "email": "s@h.edu.ng", "password": "Student@1234",
                 "role": "student", "student_id": "NSUK/1/1"},
                allow_roles=True,
            )
            with self.assertRaises(ApiError) as ctx:
                services.build_analytics(conn, student)
            self.assertEqual(ctx.exception.status, 403)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        init_db(DB_PATH)
        with database() as conn:
            clean_db(conn)
            self.admin = services.create_user(
                conn,
                {"full_name": "Admin", "email": "a@h.edu.ng", "password": "Admin@1234", "role": "admin"},
                allow_roles=True,
            )
            self.student = services.create_user(
                conn,
                {"full_name": "S User", "email": "s@h.edu.ng", "password": "Student@1234",
                 "role": "student", "student_id": "NSUK/1/1"},
                allow_roles=True,
            )
            self.hostel = services.create_hostel(
                conn, {"name": "Hall", "code": "HL", "gender": "Mixed", "total_rooms": 5}
            )

    def tearDown(self):
        pass

    def test_student_dashboard(self):
        with database() as conn:
            dash = services.build_dashboard(conn, self.student)
        self.assertEqual(dash["role"], "student")
        self.assertIn("stats", dash)
        self.assertIn("recent", dash)

    def test_admin_analytics(self):
        with database() as conn:
            analytics = services.build_analytics(conn, self.admin)
        self.assertIn("totals", analytics)
        self.assertIn("by_status", analytics)
        self.assertIn("trend", analytics)


if __name__ == "__main__":
    unittest.main()
