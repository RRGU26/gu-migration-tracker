#!/usr/bin/env python3
"""
Smart Daily Collection Checker
Runs at startup and checks if today's data collection has happened
If not, runs it automatically
"""
import sqlite3
import os
import sys
from datetime import date
import subprocess
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('startup_check.log'),
        logging.StreamHandler()
    ]
)

def check_if_ran_today():
    """Check if daily collection ran today"""
    try:
        db_path = 'data/gu_migration.db'
        if not os.path.exists(db_path):
            logging.info("Database doesn't exist, need to run collection")
            return False
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        cursor.execute("SELECT COUNT(*) FROM daily_analytics WHERE analytics_date = ?", (today,))
        count = cursor.fetchone()[0]
        
        conn.close()
        
        if count > 0:
            logging.info(f"✓ Today's data ({today}) already collected")
            return True
        else:
            logging.info(f"✗ Today's data ({today}) NOT found, need to run collection")
            return False
            
    except Exception as e:
        logging.error(f"Error checking database: {e}")
        return False

def run_daily_collection():
    """Run the daily collection"""
    try:
        logging.info("Starting daily collection...")
        result = subprocess.run([
            'python', 'src/services/daily_collection_runner.py'
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            logging.info("✓ Daily collection completed successfully")
            return True
        else:
            logging.error(f"✗ Daily collection failed: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"Error running daily collection: {e}")
        return False

if __name__ == "__main__":
    logging.info("=== GU Daily Collection Startup Check ===")
    
    # Change to the tracker directory
    os.chdir(r'C:\Users\rrose\gu-migration-tracker')
    
    # Check if today's collection has run
    if not check_if_ran_today():
        logging.info("Running daily collection now...")
        success = run_daily_collection()
        if success:
            logging.info("✓ Startup check completed successfully")
        else:
            logging.error("✗ Startup check failed")
    else:
        logging.info("✓ No action needed, today's data already collected")