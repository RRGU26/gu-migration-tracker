#!/bin/bash

# Initialize the database
echo "Setting up RR GU Analytic Tracker..."
python main.py --mode setup

# Clear mock data on first run and start fresh tracking
if [ ! -f "data/real_tracking_started.flag" ]; then
    echo "Clearing mock data and starting real tracking..."
    python scripts/clear_mock_data.py
    touch data/real_tracking_started.flag
    echo "✅ Real data tracking initialized"
fi

# Generate today's data snapshot
echo "Collecting today's market data..."
python main.py --mode daily

# Start background scheduler for automated daily reports
echo "Starting background scheduler..."
nohup python main.py --mode scheduler > logs/scheduler.log 2>&1 &
SCHEDULER_PID=$!
echo "Scheduler started with PID: $SCHEDULER_PID"

# Create PID file for cleanup
echo $SCHEDULER_PID > data/scheduler.pid

# Start the dashboard
echo "Starting dashboard server..."
cd dashboard

# Set production environment
export FLASK_ENV=production

# Create cleanup handler for scheduler
trap 'echo "Stopping scheduler..."; kill $SCHEDULER_PID 2>/dev/null; rm -f ../data/scheduler.pid' EXIT

# Start the Flask app
exec python app.py