"""Threaded HTTP server: JSON API plus static single-page frontend."""
from __future__ import annotations

import json
import mimetypes
import sqlite3
import sys
import traceback
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import services
from .api import dispatch
from .config import APP_NAME, DB_PATH, MAX_JSON_BYTES, PUBLIC_DIR
from .db import database, init_db
from .errors import ApiError
from .seed import seed_database

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
}


class HostelHubServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, db_path: Path):
        self.db_path = Path(db_path)
        super().__init__(address, handler)


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "HostelHub/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ verbs
    def do_GET(self):
        self._handle("GET")

    def do_HEAD(self):
        self._handle("HEAD")

    def do_POST(self):
        self._handle("POST")

    def do_PATCH(self):
        self._handle("PATCH")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_OPTIONS(self):
        self._send_json(204, {}, extra_headers={"Allow": "GET, HEAD, POST, PATCH, DELETE, OPTIONS"})

    # ---------------------------------------------------------------- routing
    def _handle(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path.startswith("/api/"):
            self._handle_api(method, path, parsed.query)
        elif method in ("GET", "HEAD"):
            self._serve_static(path, include_body=method == "GET")
        else:
            self._send_json(404, {"error": "Not found."})

    def _handle_api(self, method: str, path: str, raw_query: str) -> None:
        query = {key: values[0] for key, values in parse_qs(raw_query).items() if values}
        try:
            body = self._read_json_body(method)
            self._check_origin(method)
            token = self._session_token()
            with database(self.server.db_path) as conn:
                user = services.resolve_session(conn, token)
                status, payload, new_token = dispatch(
                    conn, method, path, query, body, user, token
                )
        except ApiError as exc:
            self._send_json(exc.status, exc.to_dict())
            return
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Request body is not valid JSON."})
            return
        except sqlite3.IntegrityError as exc:
            print(f"[db] integrity error: {exc}", file=sys.stderr)
            self._send_json(409, {"error": "That change conflicts with existing data."})
            return
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            traceback.print_exc()
            self._send_json(500, {"error": "An unexpected server error occurred."})
            return
        self._send_json(status, payload, token=new_token)

    # --------------------------------------------------------------- helpers
    def _read_json_body(self, method: str) -> dict:
        if method not in ("POST", "PATCH", "DELETE"):
            return {}
        length_header = self.headers.get("Content-Length")
        if not length_header:
            return {}
        try:
            length = int(length_header)
        except ValueError:
            raise ApiError(400, "Invalid Content-Length header.") from None
        if length <= 0:
            return {}
        if length > MAX_JSON_BYTES:
            raise ApiError(413, "Request body is too large.")
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type and content_type != "application/json":
            raise ApiError(415, "Send the request body as application/json.")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ApiError(400, "Request body must be a JSON object.")
        return data

    def _check_origin(self, method: str) -> None:
        if method not in ("POST", "PATCH", "DELETE"):
            return
        origin = self.headers.get("Origin")
        if not origin:
            return
        host = self.headers.get("Host", "")
        if not host or urlsplit(origin).netloc.lower() != host.lower():
            raise ApiError(403, "Cross-origin request blocked.")

    def _session_token(self) -> str | None:
        authorization = self.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip() or None
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        try:
            cookies = SimpleCookie()
            cookies.load(cookie_header)
            morsel = cookies.get("hfr_session")
            return morsel.value if morsel else None
        except Exception:
            return None

    def _send_json(
        self,
        status: int,
        payload,
        *,
        token: str | None = None,
        extra_headers: dict | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        if token is not None:
            if token == "":
                self.send_header(
                    "Set-Cookie",
                    "hfr_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
                )
            else:
                self.send_header(
                    "Set-Cookie",
                    f"hfr_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800",
                )
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD" and status != 204:
            self.wfile.write(body)

    def _serve_static(self, path: str, *, include_body: bool = True) -> None:
        relative = path.lstrip("/") or "index.html"
        candidate = (PUBLIC_DIR / relative).resolve()
        try:
            candidate.relative_to(PUBLIC_DIR.resolve())
        except ValueError:
            self._send_json(404, {"error": "Not found."})
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists() or not candidate.is_file():
            # Unknown extension-less paths fall back to the SPA shell.
            if "." not in Path(relative).name:
                candidate = PUBLIC_DIR / "index.html"
            else:
                self._send_json(404, {"error": "File not found."})
                return
        try:
            content = candidate.read_bytes()
        except OSError:
            self._send_json(500, {"error": "Could not read that file."})
            return
        content_type = MIME_TYPES.get(
            candidate.suffix.lower(), mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        )
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if include_body:
            self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        if self.path.startswith("/api/health"):
            return
        sys.stdout.write(
            f"[{self.log_date_time_string()}] {self.address_string()} {format % args}\n"
        )


def create_server(host: str, port: int, db_path: Path | str = DB_PATH) -> HostelHubServer:
    init_db(db_path)
    return HostelHubServer((host, port), RequestHandler, Path(db_path))


def ensure_seed(db_path: Path | str = DB_PATH) -> dict:
    init_db(db_path)
    with database(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count:
            return {"seeded": False, "reason": "Database already contains users."}
        return seed_database(conn)


def run(host: str, port: int, db_path: Path | str = DB_PATH, *, auto_seed: bool = True) -> None:
    init_db(db_path)
    if auto_seed:
        result = ensure_seed(db_path)
        if result.get("seeded"):
            print(f"[seed] Created demo data with {result['reports']} reports.")
    server = HostelHubServer((host, port), RequestHandler, Path(db_path))
    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
    print()
    print(f"  {APP_NAME} is running at http://{display_host}:{port}")
    print("  Demo login: student@hostelhub.edu.ng / Student@123")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
