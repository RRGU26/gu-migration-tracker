#!/usr/bin/env python3
"""
WSGI Entry Point for GU Migration Tracker Dashboard
"""
import os
import sys

# Add the dashboard directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard'))

# Import the Flask app
from app import app

# This is what Gunicorn will use
if __name__ == "__main__":
    app.run()