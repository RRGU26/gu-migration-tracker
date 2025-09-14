#!/usr/bin/env python3
"""
Database backup and restore system for Railway deployments
Ensures data persistence across deployments
"""
import os
import json
import sqlite3
from datetime import datetime, date, timedelta
import base64

class DatabaseBackup:
    def __init__(self, db_path='data/gu_migration.db'):
        self.db_path = db_path
        self.backup_file = 'data/database_backup.json'
        
    def export_to_json(self):
        """Export database to JSON for persistence"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        backup_data = {
            'backup_date': datetime.now().isoformat(),
            'tables': {}
        }
        
        # Get all tables
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            cursor = conn.execute(f"SELECT * FROM {table}")
            rows = [dict(row) for row in cursor.fetchall()]
            backup_data['tables'][table] = rows
            
        conn.close()
        
        # Save to file
        with open(self.backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
            
        print(f"Database backed up to {self.backup_file}")
        return backup_data
        
    def restore_from_json(self):
        """Restore database from JSON backup"""
        if not os.path.exists(self.backup_file):
            print("No backup file found")
            return False
            
        with open(self.backup_file, 'r') as f:
            backup_data = json.load(f)
            
        print(f"Restoring from backup dated: {backup_data['backup_date']}")
        
        conn = sqlite3.connect(self.db_path)
        
        for table_name, rows in backup_data['tables'].items():
            if not rows:
                continue
                
            # Clear existing data
            conn.execute(f"DELETE FROM {table_name}")
            
            # Insert backup data
            for row in rows:
                columns = ', '.join(row.keys())
                placeholders = ', '.join(['?' for _ in row])
                values = list(row.values())
                
                conn.execute(
                    f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                    values
                )
                
        conn.commit()
        conn.close()
        
        print("Database restored successfully")
        return True
        
    def get_recent_data_for_seeding(self):
        """Generate SQL insert statements for last 7 days of data"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Get last 7 days of daily_analytics
        seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
        cursor = conn.execute("""
            SELECT * FROM daily_analytics 
            WHERE analytics_date >= ? 
            ORDER BY analytics_date DESC
        """, (seven_days_ago,))
        
        rows = cursor.fetchall()
        
        if rows:
            print(f"Found {len(rows)} days of recent data")
            
            # Generate INSERT statement
            insert_sql = """
            INSERT OR REPLACE INTO daily_analytics (
                analytics_date, eth_price_usd, 
                origins_floor_eth, origins_supply, origins_market_cap_usd, origins_floor_change_24h,
                undead_floor_eth, undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                total_migrations, migration_percent, price_ratio, combined_market_cap_usd,
                daily_new_migrations
            ) VALUES """
            
            values = []
            for row in rows:
                values.append(f"""
            ('{row['analytics_date']}', {row['eth_price_usd']}, 
             {row['origins_floor_eth']}, {row['origins_supply']}, {row['origins_market_cap_usd']}, {row['origins_floor_change_24h']},
             {row['undead_floor_eth']}, {row['undead_supply']}, {row['undead_market_cap_usd']}, {row['undead_floor_change_24h']},
             {row['total_migrations']}, {row['migration_percent']}, {row['price_ratio']}, {row['combined_market_cap_usd']},
             {row['daily_new_migrations']})""")
            
            full_sql = insert_sql + ','.join(values)
            
            # Save to file for use in fix_railway_data.py
            with open('data/recent_data_seed.sql', 'w') as f:
                f.write(full_sql)
                
            print("Seed SQL saved to data/recent_data_seed.sql")
            
        conn.close()

if __name__ == "__main__":
    backup = DatabaseBackup()
    
    # Export current database
    backup.export_to_json()
    
    # Generate seed SQL
    backup.get_recent_data_for_seeding()