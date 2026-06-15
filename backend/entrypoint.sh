#!/bin/sh
set -e

echo "Waiting for Postgres..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        host=os.environ['POSTGRES_HOST'],
        port=os.environ.get('POSTGRES_PORT', 5432),
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
    )
    sys.exit(0)
except Exception:
    sys.exit(1)
"; do
  sleep 1
done
echo "Postgres is up"

echo "Running migrations..."
flask db upgrade

echo "Starting gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 1 \
  --threads 4 \
  --access-logfile - \
  --error-logfile - \
  wsgi:app