#!/bin/sh
set -e

echo "Waiting for Postgres..."
python - <<'EOF'
import os, socket, time, sys
host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", 5432))
deadline = time.time() + 30
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print("Postgres is up")
            sys.exit(0)
    except OSError:
        time.sleep(1)
print("Timed out waiting for Postgres", file=sys.stderr)
sys.exit(1)
EOF

echo "Running migrations..."
flask db upgrade

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 --access-logfile - --error-logfile - wsgi:app