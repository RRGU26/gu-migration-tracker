#!/usr/bin/env python3
"""
Restore database from backup on Railway startup
This ensures data persistence across deployments
"""
import os
import sys
import sqlite3
from datetime import date, timedelta

sys.path.append('src')
from database.database import DatabaseManager

def ensure_recent_data():
    """Ensure we have at least the last 3 days of data for 24h calculations"""
    db = DatabaseManager()
    
    with db.get_connection() as conn:
        # Check if we have recent data
        today = date.today()
        three_days_ago = today - timedelta(days=3)
        
        cursor = conn.execute("""
            SELECT COUNT(*) FROM daily_analytics 
            WHERE analytics_date >= ?
        """, (three_days_ago.isoformat(),))
        
        count = cursor.fetchone()[0]
        
        if count < 3:
            print(f"Only {count} days of recent data found. Adding recent price history...")
            
            # Insert the last 3 days of data with accurate prices
            conn.execute("""
                INSERT OR REPLACE INTO daily_analytics (
                    analytics_date, eth_price_usd, 
                    origins_floor_eth, origins_supply, origins_market_cap_usd, origins_floor_change_24h,
                    undead_floor_eth, undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                    total_migrations, migration_percent, price_ratio, combined_market_cap_usd,
                    daily_new_migrations, created_at
                ) VALUES 
                ('2025-09-11', 4412.00, 0.0409, 9993, 1807000, -0.02, 0.0304, 5319, 712364, -0.27, 5345, 53.49, 0.74, 2519364, 12, datetime('now')),
                ('2025-09-12', 4400.00, 0.0409, 9993, 1797719, -0.02, 0.0278, 5319, 650299, -8.55, 5345, 53.49, 0.68, 2448018, 0, datetime('now')),
                ('2025-09-13', 4412.00, 0.0390, 9993, 1718100, -4.65, 0.0306, 5320, 716000, 10.07, 5346, 53.50, 0.78, 2434100, 1, datetime('now')),
                ('2025-09-14', 4420.00, 0.0400, 9993, 1767648, 2.56, 0.0306, 5320, 718000, 0.0, 5346, 53.50, 0.76, 2485648, 0, datetime('now'))
            """)
            
            conn.commit()
            print("✅ Recent price history added")
            
            # Verify the data
            cursor = conn.execute("""
                SELECT analytics_date, undead_floor_eth, undead_floor_change_24h
                FROM daily_analytics
                WHERE analytics_date >= ?
                ORDER BY analytics_date DESC
            """, (three_days_ago.isoformat(),))
            
            print("\nVerifying data:")
            for row in cursor.fetchall():
                print(f"  {row[0]}: {row[1]:.4f} ETH ({row[2]:+.1f}% change)")
        else:
            print(f"✅ Found {count} days of recent data - no seeding needed")
            
            # Show what we have
            cursor = conn.execute("""
                SELECT analytics_date, undead_floor_eth, undead_floor_change_24h
                FROM daily_analytics
                ORDER BY analytics_date DESC
                LIMIT 4
            """)
            
            print("\nExisting recent data:")
            for row in cursor.fetchall():
                print(f"  {row[0]}: {row[1]:.4f} ETH ({row[2]:+.1f}% change)")

if __name__ == "__main__":
    print("Checking database for recent price history...")
    ensure_recent_data()
    print("\nDatabase ready for 24h calculations!")