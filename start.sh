#!/bin/bash

# Initialize the database
echo "Setting up GU Migration Tracker..."
python main.py --mode setup

# Start the dashboard
echo "Starting dashboard server..."
cd dashboard
python app.py