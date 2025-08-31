#!/bin/bash

# Initialize the database
echo "Setting up GU Migration Tracker..."
python main.py --mode setup

# Generate initial mock data report (fast startup for Railway)
echo "Generating initial dashboard data..."
python main.py --mode test

# Start the dashboard
echo "Starting dashboard server..."
cd dashboard

# Set production environment
export FLASK_ENV=production

# Start the Flask app
exec python app.py