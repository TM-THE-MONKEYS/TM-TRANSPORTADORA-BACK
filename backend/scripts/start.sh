#!/bin/bash
set -e

echo "Starting TM Transportadora Backend"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Seed só em ambiente local/dev. Em produção o script no-op e não toca na conta admin.
if [ "${APP_ENV:-development}" != "production" ]; then
  echo "Seeding database (non-production)..."
  python scripts/seed.py
else
  echo "Skipping seed in production (admin account untouched)."
fi

# Start the server
echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
