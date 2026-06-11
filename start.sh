#!/bin/bash
echo "Starting GU Analytics Tracker..."

mkdir -p data logs

# Rebuild DB from committed history seed (Railway's disk is ephemeral)
python bootstrap_db.py || echo "Bootstrap warning, continuing..."

export FLASK_ENV=production
export PORT=${PORT:-8000}

# Single worker + threads: the in-app hourly collector must run exactly once.
echo "Starting production server on port $PORT..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120 --keep-alive 2 wsgi:app
