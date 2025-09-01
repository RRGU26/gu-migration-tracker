#!/usr/bin/env python3
"""
Clear mock historical data and start fresh with real tracking
"""
import os
import sys
import sqlite3
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def clear_mock_data():
    """Clear all mock historical data from database"""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gu_migration.db')
    
    if not os.path.exists(db_path):
        print("Database not found. Nothing to clear.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear all historical snapshots
        cursor.execute("DELETE FROM daily_snapshots")
        snapshots_deleted = cursor.rowcount
        
        # Clear all migrations
        cursor.execute("DELETE FROM migrations")
        migrations_deleted = cursor.rowcount
        
        # Clear all trades
        cursor.execute("DELETE FROM trades")
        trades_deleted = cursor.rowcount
        
        conn.commit()
        
        print(f"✅ Cleared mock data:")
        print(f"   - {snapshots_deleted} historical snapshots removed")
        print(f"   - {migrations_deleted} mock migrations removed")
        print(f"   - {trades_deleted} mock trades removed")
        print(f"\n📊 Database is now ready for real data tracking starting from {datetime.now().strftime('%Y-%m-%d')}")
        
        # Remove the backfill flag so it won't regenerate mock data
        flag_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'historical_backfilled.flag')
        if os.path.exists(flag_path):
            os.remove(flag_path)
            print("✅ Removed backfill flag - no more mock data generation")
            
    except Exception as e:
        print(f"❌ Error clearing data: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    clear_mock_data()