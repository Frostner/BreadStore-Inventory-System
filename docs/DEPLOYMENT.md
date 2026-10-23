# Deployment guide and basic cloud concepts

## Development vs deployed applications

For local development, run:

```bash
python -m uvicorn app:app --reload
```

For a **single-instance** hosted application, use an ASGI process command similar to:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

In both cases, install packages using `pip install -r requirements.txt`. Port numbers, HTTPS, proxy configuration and persistent storage depend on the hosting provider. Hosting has **not** been set up as part of this generated project, so there is no live demo URL yet.

## Important: persist the SQLite database

SQLite is a single file, by default `data/breadstore.db`. If deployed on a free or ephemeral service, a redeploy or machine restart **may erase that file**. Use hosting with a **persistent storage volume** that survives restarts, or migrate to a managed server database such as PostgreSQL for multiple instances.

A basic persistent-volume configuration might set:

```env
DB_PATH=/persistent-disk/breadstore.db
COOKIE_SECURE=true
ADMIN_EMAIL=admin@yourdomain.example
ADMIN_PASSWORD=CREATE_A_UNIQUE_LONG_PASSWORD_BEFORE_INITIAL_START
SEED_DEMO=false
```

Set these values in the hosting service's private environment settings, **not** in public source code or a GitHub-tracked `.env` file.

For a portfolio **public demo** containing sample stock only, still choose HTTPS and persistent hosting. Never copy real customer or store business data into a public demo.

## TLS/HTTPS and cookies

- Deploy behind a trustworthy HTTPS load balancer or reverse proxy.
- Set `COOKIE_SECURE=true` so browsers only send admin cookies over HTTPS.
- Limit public access to authorized administrators; this project has no self-registration.
- Restrict admin access to HTTPS and protect the hosting dashboard's login and keys.
- If a reverse proxy changes Host/Origin values, ensure it forwards the intended domain consistently; the app rejects cross-origin writes.

## Recommended backup procedure

1. Stop new writes briefly or use SQLite's supported online backup API.
2. Back up `breadstore.db` into a safe, access-controlled folder or backup service.
3. Test restoring the backup into a separate environment.
4. Keep multiple dated backups and verify restoration regularly.
5. Protect backup files because they include operational business data and password hashes.

**Simple local backup** for a small installation with Python:

```python
from sqlite3 import connect
with connect('data/breadstore.db') as src, connect('breadstore-backup.db') as dst:
    src.backup(dst)
```

Run this from the project folder. Move the resulting backup to a secure destination; do not commit it to public GitHub.

## Cloud assessment preparation

Be able to explain the following:

- **Hosting:** where the Python application process runs.
- **Server:** the FastAPI process handles frontend requests and SQL operations.
- **Environment variables:** how secrets and storage settings are configured without hardcoding them.
- **Database persistence:** why a writable volume matters to SQLite.
- **Logs:** how server startup and error logs help diagnose failure.
- **HTTPS:** why login sessions must be encrypted in transit.
- **Monitoring:** the `/api/health` endpoint can help confirm API/database connectivity.

## Important limitations

Deployment is an exercise that must be performed with your own account and URL. A host-specific deployment manifest has not been tested here. Before using the system for an actual store, consider professional security review, access roles, backups, logging retention, patching, secrets rotation, HTTPS, and an appropriate database choice.
