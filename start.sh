#!/bin/bash

echo "Starting RR GU Analytic Tracker on Railway..."

# Create necessary directories
mkdir -p data logs

# Initialize the database with schema and initial data
echo "Setting up database..."
python init_database.py || echo "Database initialization warning, continuing..."

# Try to collect fresh data (but don't fail if rate limited)
echo "Attempting data collection..."
timeout 20 python src/services/daily_collection_runner.py 2>/dev/null || echo "Data collection skipped (API rate limited or timeout)"

# Start the dashboard in production mode
echo "Starting dashboard server..."
cd dashboard

# Set production environment
export FLASK_ENV=production
export PORT=${PORT:-8000}
export DB_INITIALIZED=true

# Start the Flask app directly
exec python app.py