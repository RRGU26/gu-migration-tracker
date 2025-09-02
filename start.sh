#!/bin/bash

echo "Starting RR GU Analytic Tracker on Railway..."

# Create necessary directories
mkdir -p data logs

# Initialize the database schema only once
echo "Setting up database schema..."
python -c "
import sys
import os
sys.path.append('src')

# Set environment variable to prevent repeated DB initialization
os.environ['DB_INITIALIZED'] = 'true'

from src.database.database import DatabaseManager
db = DatabaseManager('data/gu_migration.db')
print('Database initialized successfully')
" || echo "Database initialization failed, continuing..."

# Try to collect initial data but don't fail if rate limited
echo "Attempting initial data collection..."
timeout 30 python src/services/daily_collection_runner.py 2>/dev/null || echo "Initial data collection skipped (likely rate limited)"

# Start the dashboard in production mode
echo "Starting dashboard server..."
cd dashboard

# Set production environment
export FLASK_ENV=production
export PORT=${PORT:-8000}
export DB_INITIALIZED=true

# Start the Flask app directly
exec python app.py