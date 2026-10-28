#!/bin/sh
# Backend entrypoint: wait for Postgres, then start the API with uvicorn.
set -eu

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"

printf '%s\n' "Waiting for database at ${DB_HOST}:${DB_PORT}..."
DB_HOST="$DB_HOST" DB_PORT="$DB_PORT" python -c "
import os, socket, time
host, port = os.environ['DB_HOST'], int(os.environ['DB_PORT'])
while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        time.sleep(1)
"
printf '%s\n' "Database is up - starting uvicorn"
printf '%s\n' "Seeding default admin (skips if unset or already exists)..."
python add_admin.py
python add_demodata.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
