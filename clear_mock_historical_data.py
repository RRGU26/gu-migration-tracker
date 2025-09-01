#!/usr/bin/env python3
"""
Clear mock historical data and keep only real data from yesterday onwards
"""
import sys
import os
from datetime import date, timedelta

# Add src to path
sys.path.append('src')

from src.database.database import DatabaseManager

def clear_mock_historical_data():
    """Clear all data before yesterday (which is mock data)"""
    print("Clearing Mock Historical Data...")
    print("=" * 40)
    
    try:
        db = DatabaseManager('data/gu_migration.db')
        yesterday = date.today() - timedelta(days=1)
        yesterday_str = yesterday.isoformat()
        
        print(f"Keeping data from: {yesterday_str} onwards")
        print(f"Clearing data before: {yesterday_str}")
        
        with db.get_connection() as conn:
            # Check what data exists before clearing
            cursor = conn.execute("""
                SELECT COUNT(*) as count, MIN(snapshot_date) as earliest, MAX(snapshot_date) as latest
                FROM daily_snapshots
            """)
            before_stats = cursor.fetchone()
            print(f"\nBefore clearing:")
            print(f"  Total snapshots: {before_stats['count']}")
            print(f"  Date range: {before_stats['earliest']} to {before_stats['latest']}")
            
            # Clear mock data (everything before yesterday)
            cursor = conn.execute("""
                DELETE FROM daily_snapshots 
                WHERE snapshot_date < ?
            """, (yesterday_str,))
            
            deleted_count = cursor.rowcount
            print(f"\nDeleted {deleted_count} mock snapshot records")
            
            # Also clear mock migration records if any
            cursor = conn.execute("""
                DELETE FROM migrations 
                WHERE migration_date < ?
            """, (yesterday_str,))
            
            migration_deleted = cursor.rowcount
            print(f"Deleted {migration_deleted} mock migration records")
            
            # Clear old API logs to clean up
            cursor = conn.execute("""
                DELETE FROM api_logs 
                WHERE called_at < datetime('now', '-7 days')
            """)
            
            api_deleted = cursor.rowcount
            print(f"Deleted {api_deleted} old API log records")
            
            conn.commit()
            
            # Check what remains
            cursor = conn.execute("""
                SELECT COUNT(*) as count, MIN(snapshot_date) as earliest, MAX(snapshot_date) as latest
                FROM daily_snapshots
            """)
            after_stats = cursor.fetchone()
            print(f"\nAfter clearing:")
            print(f"  Remaining snapshots: {after_stats['count']}")
            if after_stats['count'] > 0:
                print(f"  Date range: {after_stats['earliest']} to {after_stats['latest']}")
            else:
                print(f"  No snapshots remaining - ready for fresh real data")
            
            # Show what real data we have by date
            cursor = conn.execute("""
                SELECT snapshot_date, COUNT(*) as count
                FROM daily_snapshots
                GROUP BY snapshot_date
                ORDER BY snapshot_date DESC
            """)
            real_data = cursor.fetchall()
            
            print(f"\nReal data by date:")
            if real_data:
                for row in real_data:
                    print(f"  {row['snapshot_date']}: {row['count']} snapshots")
            else:
                print(f"  No real data yet - system ready for daily collection")
        
        print(f"\nSUCCESS: Mock data cleared, only real data remains!")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to clear mock data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = clear_mock_historical_data()
    print(f"\nCleanup: {'SUCCESS' if success else 'FAILED'}")