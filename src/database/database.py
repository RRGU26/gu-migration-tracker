import sqlite3
import os
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
import json
from contextlib import contextmanager

class DatabaseManager:
    _initialized = False  # Class variable to track initialization
    
    def __init__(self, db_path: str = "data/gu_migration.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Only initialize once per process
        if not DatabaseManager._initialized or os.environ.get('DB_FORCE_INIT'):
            self.init_database()
            DatabaseManager._initialized = True
    
    def init_database(self):
        """Initialize database with schema - only runs once"""
        try:
            # Check if database already exists and has tables
            if os.path.exists(self.db_path):
                with self.get_connection() as conn:
                    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    if len(tables) >= 5:  # We expect at least 5 main tables
                        self.logger.debug("Database already initialized with tables")
                        return
            
            # Get the absolute path to schema.sql
            current_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(current_dir, 'schema.sql')
            
            with open(schema_path, 'r') as f:
                schema = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema)
                conn.commit()
                
            self.logger.info("Database schema created successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            # Don't raise if DB already exists
            if "already exists" not in str(e):
                raise
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_collection_id(self, slug: str) -> Optional[int]:
        """Get collection ID by slug"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT id FROM collections WHERE slug = ?", (slug,))
            result = cursor.fetchone()
            return result['id'] if result else None
    
    def get_collections(self) -> List[Dict]:
        """Get all collections"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM collections ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]
    
    def save_daily_snapshot(self, collection_id: int, snapshot_data: Dict) -> bool:
        """Save daily collection snapshot"""
        try:
            with self.get_connection() as conn:
                # Use INSERT OR REPLACE to handle duplicate dates
                conn.execute("""
                    INSERT OR REPLACE INTO daily_snapshots (
                        collection_id, snapshot_date, total_supply, holders_count,
                        floor_price_eth, floor_price_usd, market_cap_eth, market_cap_usd,
                        volume_24h_eth, volume_24h_usd, volume_7d_eth, volume_7d_usd,
                        listed_count, listed_percentage, average_price_eth, average_price_usd,
                        num_sales_24h
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    collection_id,
                    snapshot_data.get('snapshot_date', date.today()),
                    snapshot_data.get('total_supply'),
                    snapshot_data.get('holders_count'),
                    snapshot_data.get('floor_price_eth'),
                    snapshot_data.get('floor_price_usd'),
                    snapshot_data.get('market_cap_eth'),
                    snapshot_data.get('market_cap_usd'),
                    snapshot_data.get('volume_24h_eth'),
                    snapshot_data.get('volume_24h_usd'),
                    snapshot_data.get('volume_7d_eth'),
                    snapshot_data.get('volume_7d_usd'),
                    snapshot_data.get('listed_count'),
                    snapshot_data.get('listed_percentage'),
                    snapshot_data.get('average_price_eth'),
                    snapshot_data.get('average_price_usd'),
                    snapshot_data.get('num_sales_24h')
                ))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save daily snapshot: {e}")
            return False
    
    def get_latest_snapshot(self, collection_id: int) -> Optional[Dict]:
        """Get latest snapshot for collection"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM daily_snapshots 
                WHERE collection_id = ? 
                ORDER BY snapshot_date DESC 
                LIMIT 1
            """, (collection_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_snapshot_by_date(self, collection_id: int, snapshot_date: date) -> Optional[Dict]:
        """Get snapshot for specific date"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM daily_snapshots 
                WHERE collection_id = ? AND snapshot_date = ?
            """, (collection_id, snapshot_date))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_historical_snapshots(self, collection_id: int, days: int = 30) -> List[Dict]:
        """Get historical snapshots for analysis"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM daily_snapshots 
                WHERE collection_id = ? 
                ORDER BY snapshot_date DESC 
                LIMIT ?
            """, (collection_id, days))
            return [dict(row) for row in cursor.fetchall()]
    
    def save_migration(self, token_id: str, from_collection_id: int, 
                      to_collection_id: int, migration_date: date,
                      transaction_hash: str = None, block_number: int = None) -> bool:
        """Save detected migration"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO migrations (
                        token_id, from_collection_id, to_collection_id, 
                        migration_date, transaction_hash, block_number
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (token_id, from_collection_id, to_collection_id, 
                      migration_date, transaction_hash, block_number))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save migration: {e}")
            return False
    
    def get_migrations_by_date(self, migration_date: date) -> List[Dict]:
        """Get migrations for specific date"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT m.*, c1.name as from_collection, c2.name as to_collection
                FROM migrations m
                JOIN collections c1 ON m.from_collection_id = c1.id
                JOIN collections c2 ON m.to_collection_id = c2.id
                WHERE m.migration_date = ?
                ORDER BY m.detected_at DESC
            """, (migration_date,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_total_migrations(self) -> int:
        """Get total number of migrations"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM migrations")
            return cursor.fetchone()['count']
    
    def get_migration_stats(self, days: int = 7) -> Dict:
        """Get migration statistics for the past N days"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    migration_date,
                    COUNT(*) as daily_count,
                    from_collection_id,
                    to_collection_id
                FROM migrations 
                WHERE migration_date >= date('now', '-{} days')
                GROUP BY migration_date, from_collection_id, to_collection_id
                ORDER BY migration_date DESC
            """.format(days))
            
            results = [dict(row) for row in cursor.fetchall()]
            
            # Calculate total and daily averages
            total_migrations = sum(r['daily_count'] for r in results)
            avg_daily = total_migrations / max(days, 1)
            
            return {
                'total_migrations': total_migrations,
                'daily_average': avg_daily,
                'daily_breakdown': results
            }
    
    def save_token_holders(self, collection_id: int, token_holders: List[Dict], 
                          snapshot_date: date) -> bool:
        """Save token holder data for migration detection"""
        try:
            with self.get_connection() as conn:
                # Clear existing holders for this date
                conn.execute("""
                    DELETE FROM token_holders 
                    WHERE collection_id = ? AND snapshot_date = ?
                """, (collection_id, snapshot_date))
                
                # Insert new holders
                holders_data = [
                    (collection_id, holder['token_id'], holder['holder_address'], snapshot_date)
                    for holder in token_holders
                ]
                
                conn.executemany("""
                    INSERT INTO token_holders (collection_id, token_id, holder_address, snapshot_date)
                    VALUES (?, ?, ?, ?)
                """, holders_data)
                
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save token holders: {e}")
            return False
    
    def get_token_holders(self, collection_id: int, snapshot_date: date) -> List[Dict]:
        """Get token holders for specific date"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT token_id, holder_address 
                FROM token_holders 
                WHERE collection_id = ? AND snapshot_date = ?
            """, (collection_id, snapshot_date))
            return [dict(row) for row in cursor.fetchall()]
    
    def log_api_call(self, endpoint: str, status_code: int, response_time_ms: int, 
                    error_message: str = None) -> bool:
        """Log API call for monitoring"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO api_logs (endpoint, status_code, response_time_ms, error_message)
                    VALUES (?, ?, ?, ?)
                """, (endpoint, status_code, response_time_ms, error_message))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to log API call: {e}")
            return False
    
    def create_alert(self, alert_type: str, severity: str, message: str, 
                    data: Dict = None) -> bool:
        """Create system alert"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO alerts (alert_type, severity, message, data)
                    VALUES (?, ?, ?, ?)
                """, (alert_type, severity, message, json.dumps(data) if data else None))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to create alert: {e}")
            return False
    
    def get_unresolved_alerts(self) -> List[Dict]:
        """Get unresolved alerts"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM alerts 
                WHERE resolved = FALSE 
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def resolve_alert(self, alert_id: int) -> bool:
        """Mark alert as resolved"""
        try:
            with self.get_connection() as conn:
                conn.execute("UPDATE alerts SET resolved = TRUE WHERE id = ?", (alert_id,))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to resolve alert: {e}")
            return False