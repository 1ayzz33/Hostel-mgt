"""Application configuration for HostelHub."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("HOSTELHUB_DB", DATA_DIR / "hostelhub.db")).resolve()

APP_NAME = "HostelHub"
APP_TAGLINE = "Hostel facilities, reported and resolved."
HOST = os.environ.get("HOSTELHUB_HOST", "127.0.0.1")
PORT = int(os.environ.get("HOSTELHUB_PORT", "8000"))

SESSION_DAYS = 7
MAX_PHOTO_BYTES = 2_000_000
MAX_JSON_BYTES = 6_000_000
PBKDF2_ITERATIONS = 260_000

CATEGORIES = [
    "Electrical",
    "Plumbing",
    "Furniture",
    "Internet / ICT",
    "Sanitation",
    "Security",
    "HVAC / Ventilation",
    "Other",
]

PRIORITIES = ["low", "medium", "high", "urgent"]
STATUSES = ["submitted", "assigned", "in_progress", "resolved", "closed", "reopened"]
ROLES = ["student", "staff", "admin"]
SLA_HOURS = {"low": 72, "medium": 48, "high": 24, "urgent": 6}
