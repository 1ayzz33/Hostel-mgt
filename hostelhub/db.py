"""SQLite connection management and schema definition."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS hostels (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    code          TEXT NOT NULL UNIQUE,
    gender        TEXT NOT NULL DEFAULT 'Mixed'
                  CHECK (gender IN ('Male', 'Female', 'Mixed')),
    address       TEXT NOT NULL DEFAULT '',
    warden_name   TEXT NOT NULL DEFAULT '',
    warden_phone  TEXT NOT NULL DEFAULT '',
    total_rooms   INTEGER NOT NULL DEFAULT 0 CHECK (total_rooms >= 0),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('student', 'staff', 'admin')),
    student_id    TEXT,
    phone         TEXT NOT NULL DEFAULT '',
    hostel_id     INTEGER REFERENCES hostels(id) ON DELETE SET NULL,
    room_number   TEXT NOT NULL DEFAULT '',
    department    TEXT NOT NULL DEFAULT '',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facilities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id   INTEGER NOT NULL REFERENCES hostels(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    condition   TEXT NOT NULL DEFAULT 'Good'
                CHECK (condition IN ('Good', 'Fair', 'Poor', 'Under repair')),
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ref             TEXT UNIQUE,
    student_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hostel_id       INTEGER NOT NULL REFERENCES hostels(id) ON DELETE CASCADE,
    facility_id     INTEGER REFERENCES facilities(id) ON DELETE SET NULL,
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    location        TEXT NOT NULL DEFAULT '',
    priority        TEXT NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status          TEXT NOT NULL DEFAULT 'submitted'
                    CHECK (status IN ('submitted', 'assigned', 'in_progress',
                                      'resolved', 'closed', 'reopened')),
    assigned_to     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    photo           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    resolved_at     TEXT,
    resolution_note TEXT,
    rating          INTEGER CHECK (rating BETWEEN 1 AND 5),
    feedback        TEXT
);

CREATE TABLE IF NOT EXISTS report_updates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    from_status TEXT,
    to_status   TEXT,
    is_internal INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_id  INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    message    TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS announcements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    audience   TEXT NOT NULL DEFAULT 'all'
               CHECK (audience IN ('all', 'students', 'staff', 'admin')),
    is_pinned  INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_student ON reports(student_id);
CREATE INDEX IF NOT EXISTS idx_reports_assigned ON reports(assigned_to);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);
CREATE INDEX IF NOT EXISTS idx_updates_report ON report_updates(report_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_facilities_hostel ON facilities(hostel_id);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(db_path: Path | str | None = None) -> Path:
    path = Path(db_path) if db_path else DB_PATH
    with connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


@contextmanager
def database(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def as_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]
