"""HostelHub entry point.

Usage:
    python app.py                 # start on http://127.0.0.1:8000
    python app.py --reset         # rebuild the demo database and start
    python app.py --port 9000     # choose another port
"""
from __future__ import annotations

import argparse

from hostelhub.config import DB_PATH, HOST, PORT
from hostelhub.db import database, init_db
from hostelhub.seed import seed_database
from hostelhub.server import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the HostelHub platform.")
    parser.add_argument("--host", default=HOST, help="Bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=PORT, help="Port (default: 8000).")
    parser.add_argument("--reset", action="store_true", help="Rebuild the demo database.")
    parser.add_argument("--no-seed", action="store_true", help="Do not seed an empty database.")
    args = parser.parse_args()

    init_db(DB_PATH)
    if args.reset:
        with database(DB_PATH) as conn:
            result = seed_database(conn, reset=True)
        print(f"[seed] Rebuilt demo data with {result.get('reports', 0)} reports.")

    run(args.host, args.port, DB_PATH, auto_seed=not args.no_seed)


if __name__ == "__main__":
    main()
