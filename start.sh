#!/bin/bash

# Initialize the database
echo "Setting up GU Migration Tracker..."
python main.py --mode setup

# Check if we need to backfill historical data
if [ ! -f "data/historical_backfilled.flag" ]; then
    echo "Backfilling 30 days of historical market data..."
    python scripts/backfill_historical_data.py
    touch data/historical_backfilled.flag
    echo "✅ Historical data backfill completed"
else
    echo "Historical data already exists, skipping backfill"
fi

# Generate today's data report
echo "Generating current market data..."
python main.py --mode test

# Start the dashboard
echo "Starting dashboard server..."
cd dashboard

# Set production environment
export FLASK_ENV=production

# Start the Flask app
exec python app.py