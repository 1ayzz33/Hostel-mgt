# Setup & deployment guide

## Prerequisites

- Python 3.10 or newer (no external packages required — standard library only)
- Any modern web browser

## Run in development

```bash
cd "C:\Users\Jfx\Documents\Projects-NSUK\01-online-hostel-facilities-reporting-platform"

# Seed the demo database (optional but recommended)
python -m hostelhub.seed --reset

# Start the server
python app.py
# → http://127.0.0.1:8000
```

### Options

```
python app.py --help
  --host      Bind address (default: 127.0.0.1)
  --port      Port (default: 8000)
  --reset     Rebuild the demo database before starting
  --no-seed   Do not auto-seed an empty database
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `HOSTELHUB_DB` | `data/hostelhub.db` | SQLite database path |
| `HOSTELHUB_HOST` | `127.0.0.1` | Bind address |
| `HOSTELHUB_PORT` | `8000` | Port |

## Run the test suites

### Unit tests (no server needed)

```bash
python -m unittest tests.test_services -v
# 23 tests covering auth, reports, admin, dashboards and analytics
```

### End-to-end tests (server must be running)

Terminal 1:
```bash
python app.py --reset
```

Terminal 2:
```bash
python e2e_test.py http://127.0.0.1:8000
# exercises all three roles end to end
```

## Database

The SQLite database is created automatically on first run at `data/hostelhub.db`.
To wipe and re-seed:

```bash
python -m hostelhub.seed --reset
```

Demo accounts after seeding:

| Role | Email | Password |
|------|-------|----------|
| Student | student@hostelhub.edu.ng | Student@123 |
| Staff | grace.okafor@hostelhub.edu.ng | Staff@123 |
| Admin | admin@hostelhub.edu.ng | Admin@123 |

## Production considerations

1. **Change the demo passwords** in `hostelhub/seed.py` before any real use.
2. **Bind to `0.0.0.0`** only behind a reverse proxy (Nginx/Apache/Caddy) that
   terminates HTTPS — the built-in server is for development/demo use.
3. **Back up** `data/hostelhub.db` regularly; it is a single portable file.
4. **Set `HOSTELHUB_DB`** to a location outside the web root if you host files
   alongside the app.
5. Session cookies are `HttpOnly` and `SameSite=Lax`; enforce HTTPS in
   production so cookies are `Secure`.

## Customising behaviour

Edit `hostelhub/config.py`:

- `SLA_HOURS` — response targets per priority (urgent 6h, high 24h, medium 48h,
  low 72h by default)
- `CATEGORIES` / `PRIORITIES` / `STATUSES` / `ROLES` — domain vocabularies
- `SESSION_DAYS` — login cookie lifetime
- `MAX_PHOTO_BYTES` — photo upload ceiling (2 MB by default)

## License

MIT — free to use for academic and personal projects.
