#!/bin/bash

echo "🚀 Starting RR GU Analytic Tracker on Railway..."

# Create necessary directories
mkdir -p data logs

# Initialize the database schema
echo "📊 Setting up database schema..."
python -c "
import sys
sys.path.append('src')
from src.database.database import DatabaseManager
db = DatabaseManager('data/gu_migration.db')
print('Database initialized successfully')
"

# Run initial data collection
echo "🔄 Collecting initial data..."
python src/services/daily_collection_runner.py

# Start the dashboard in production mode
echo "🌐 Starting dashboard server..."
cd dashboard

# Set production environment
export FLASK_ENV=production
export PORT=${PORT:-8000}

# Start the Flask app with Railway port configuration
exec python -c "
import sys
import os
sys.path.append('../src')
from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f'Starting server on port {port}')
    app.run(host='0.0.0.0', port=port)
"