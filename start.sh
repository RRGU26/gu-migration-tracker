#!/bin/bash

# Initialize the database
echo "Setting up GU Migration Tracker..."
python main.py --mode setup

# Start the dashboard
echo "Starting dashboard server..."
cd dashboard

# Set production environment
export FLASK_ENV=production

# Start the Flask app
exec python app.py