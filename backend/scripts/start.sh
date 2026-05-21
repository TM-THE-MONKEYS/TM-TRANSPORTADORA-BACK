#!/bin/bash
set -e

echo "Starting TM Transportadora Backend"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Seed database (only on first run)
echo "Seeding database..."
python scripts/seed.py

# Start the server
echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
