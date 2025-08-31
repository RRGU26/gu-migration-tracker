import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict

from src.database.database import DatabaseManager
from src.api.opensea_client import OpenSeaClient, fetch_all_collections_data
from src.api.price_client import get_current_eth_price
from config.config import Config

class MigrationDetector:
    """Detects NFT migrations between GU Origins and Genuine Undead collections"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.opensea_client = OpenSeaClient()
        self.logger = logging.getLogger(__name__)
        
        # Get collection IDs
        self.origins_id = self.db.get_collection_id('gu-origins')
        self.undead_id = self.db.get_collection_id('genuine-undead')
        
        if not self.origins_id or not self.undead_id:
            raise ValueError("Collection IDs not found in database")
    
    async def detect_daily_migrations(self, target_date: date = None) -> Dict[str, any]:
        """Detect migrations for a specific date"""
        if target_date is None:
            target_date = date.today()
        
        self.logger.info(f"Detecting migrations for {target_date}")
        
        # Get previous day for comparison
        previous_date = target_date - timedelta(days=1)
        
        try:
            # Fetch current holder data for both collections
            collections_data = await fetch_all_collections_data()
            
            # Process holder data
            origins_data = collections_data.get('gu_origins', {})
            undead_data = collections_data.get('genuine_undead', {})
            
            current_origins_holders = self._extract_holder_data(origins_data.get('owners', []))
            current_undead_holders = self._extract_holder_data(undead_data.get('owners', []))
            
            # Save current holder data
            await self._save_holder_snapshots(target_date, current_origins_holders, current_undead_holders)
            
            # Get previous day's holders for comparison
            previous_origins_holders = self._get_previous_holders(self.origins_id, previous_date)
            previous_undead_holders = self._get_previous_holders(self.undead_id, previous_date)
            
            # Detect migrations
            detected_migrations = self._find_migrations(
                previous_origins_holders, current_origins_holders,
                previous_undead_holders, current_undead_holders,
                target_date
            )
            
            # Save detected migrations
            migration_count = 0
            for migration in detected_migrations:
                success = self.db.save_migration(
                    migration['token_id'],
                    migration['from_collection_id'],
                    migration['to_collection_id'],
                    migration['migration_date'],
                    migration.get('transaction_hash'),
                    migration.get('block_number')
                )
                if success:
                    migration_count += 1
            
            self.logger.info(f"Detected and saved {migration_count} migrations for {target_date}")
            
            return {
                'date': target_date,
                'migrations_detected': migration_count,
                'migrations': detected_migrations,
                'origins_holders': len(current_origins_holders),
                'undead_holders': len(current_undead_holders)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to detect migrations for {target_date}: {e}")
            self.db.create_alert(
                'migration_detection_failed',
                'ERROR',
                f"Migration detection failed for {target_date}: {str(e)}"
            )
            return {
                'date': target_date,
                'migrations_detected': 0,
                'migrations': [],
                'error': str(e)
            }
    
    def _extract_holder_data(self, owners_data: List[Dict]) -> Dict[str, str]:
        """Extract token_id -> holder_address mapping from API data"""
        holders = {}
        for owner_info in owners_data:
            token_id = owner_info.get('token_id', '')
            holder_address = owner_info.get('holder_address', '')
            if token_id and holder_address:
                holders[token_id] = holder_address.lower()  # Normalize to lowercase
        return holders
    
    async def _save_holder_snapshots(self, snapshot_date: date, 
                                   origins_holders: Dict[str, str], 
                                   undead_holders: Dict[str, str]):
        """Save holder snapshots to database"""
        # Convert to list format for database storage
        origins_list = [
            {'token_id': token_id, 'holder_address': address}
            for token_id, address in origins_holders.items()
        ]
        undead_list = [
            {'token_id': token_id, 'holder_address': address}
            for token_id, address in undead_holders.items()
        ]
        
        # Save to database
        self.db.save_token_holders(self.origins_id, origins_list, snapshot_date)
        self.db.save_token_holders(self.undead_id, undead_list, snapshot_date)
    
    def _get_previous_holders(self, collection_id: int, date_key: date) -> Dict[str, str]:
        """Get holder data for previous date from database"""
        holder_records = self.db.get_token_holders(collection_id, date_key)
        return {
            record['token_id']: record['holder_address'].lower()
            for record in holder_records
        }
    
    def _find_migrations(self, prev_origins: Dict[str, str], curr_origins: Dict[str, str],
                        prev_undead: Dict[str, str], curr_undead: Dict[str, str],
                        migration_date: date) -> List[Dict]:
        """Find tokens that migrated from Origins to Genuine Undead"""
        migrations = []
        
        # Find tokens that were in Origins yesterday but not today
        for token_id in prev_origins:
            if token_id not in curr_origins:
                # Check if this token appeared in Genuine Undead today
                if token_id in curr_undead:
                    # This looks like a migration!
                    migrations.append({
                        'token_id': token_id,
                        'from_collection_id': self.origins_id,
                        'to_collection_id': self.undead_id,
                        'migration_date': migration_date,
                        'previous_holder': prev_origins[token_id],
                        'current_holder': curr_undead[token_id],
                        'same_holder': prev_origins[token_id] == curr_undead[token_id]
                    })
        
        # Also check for tokens that might have been missed in previous snapshots
        # (tokens that are in Genuine Undead but never recorded in Origins)
        potential_migrations = []
        for token_id in curr_undead:
            if (token_id not in prev_undead and  # New to Genuine Undead
                token_id not in curr_origins and  # Not currently in Origins
                token_id not in prev_origins):    # Wasn't in Origins yesterday
                
                # This might be a migration we missed or a brand new mint
                # We'll flag it for manual review
                potential_migrations.append({
                    'token_id': token_id,
                    'status': 'potential_migration',
                    'holder': curr_undead[token_id]
                })
        
        if potential_migrations:
            self.logger.info(f"Found {len(potential_migrations)} potential migrations requiring review")
            self.db.create_alert(
                'potential_migrations_detected',
                'INFO',
                f"Found {len(potential_migrations)} potential migrations on {migration_date}",
                {'potential_migrations': potential_migrations}
            )
        
        return migrations
    
    def get_migration_summary(self, days: int = 7) -> Dict:
        """Get migration summary for the past N days"""
        return self.db.get_migration_stats(days)
    
    def calculate_migration_rate(self) -> Dict:
        """Calculate current migration rate and velocity"""
        try:
            # Get latest Origins collection data
            latest_origins = self.db.get_latest_snapshot(self.origins_id)
            if not latest_origins:
                return {'error': 'No Origins collection data available'}
            
            total_migrations = self.db.get_total_migrations()
            original_supply = latest_origins.get('total_supply', 0)
            current_supply = latest_origins.get('total_supply', 0)  # This should be updated based on migrations
            
            if original_supply == 0:
                return {'error': 'Invalid supply data'}
            
            # Calculate migration rate
            migration_rate = (total_migrations / original_supply) * 100
            remaining_tokens = original_supply - total_migrations
            
            # Calculate migration velocity (7-day average)
            weekly_stats = self.get_migration_summary(7)
            weekly_average = weekly_stats.get('daily_average', 0)
            
            # Estimate time to complete migration (if current rate continues)
            days_to_complete = remaining_tokens / max(weekly_average, 0.1)  # Avoid division by zero
            
            return {
                'total_migrations': total_migrations,
                'original_supply': original_supply,
                'migration_rate_percent': round(migration_rate, 2),
                'remaining_tokens': remaining_tokens,
                'weekly_average_daily': round(weekly_average, 1),
                'estimated_days_to_complete': round(days_to_complete, 0) if days_to_complete < 1000 else '1000+',
                'migration_velocity_trend': self._calculate_velocity_trend()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate migration rate: {e}")
            return {'error': str(e)}
    
    def _calculate_velocity_trend(self) -> str:
        """Calculate if migration velocity is increasing, decreasing, or stable"""
        try:
            # Get last 14 days of migration data
            stats_14d = self.db.get_migration_stats(14)
            daily_breakdown = stats_14d.get('daily_breakdown', [])
            
            if len(daily_breakdown) < 7:
                return 'insufficient_data'
            
            # Split into two weeks for comparison
            recent_week = daily_breakdown[:7]  # Last 7 days
            previous_week = daily_breakdown[7:14]  # Previous 7 days
            
            recent_avg = sum(d['daily_count'] for d in recent_week) / len(recent_week)
            previous_avg = sum(d['daily_count'] for d in previous_week) / len(previous_week)
            
            if previous_avg == 0:
                return 'new_activity'
            
            change_percent = ((recent_avg - previous_avg) / previous_avg) * 100
            
            if change_percent > 10:
                return 'accelerating'
            elif change_percent < -10:
                return 'decelerating'
            else:
                return 'stable'
                
        except Exception as e:
            self.logger.error(f"Failed to calculate velocity trend: {e}")
            return 'unknown'
    
    async def validate_migration(self, token_id: str, migration_date: date) -> Dict:
        """Validate a specific migration using on-chain data (if available)"""
        # This could be enhanced with Etherscan API calls to verify transfers
        # For now, we'll do basic validation using our stored data
        
        migration_records = self.db.get_migrations_by_date(migration_date)
        token_migration = next((m for m in migration_records if m['token_id'] == token_id), None)
        
        if not token_migration:
            return {'valid': False, 'reason': 'Migration record not found'}
        
        # Check if token is actually in the destination collection now
        try:
            undead_data = await self.opensea_client.get_comprehensive_collection_data('genuine-undead')
            current_owners = self._extract_holder_data(undead_data.get('owners', []))
            
            if token_id in current_owners:
                return {
                    'valid': True,
                    'token_id': token_id,
                    'current_holder': current_owners[token_id],
                    'migration_date': migration_date
                }
            else:
                return {
                    'valid': False,
                    'reason': f'Token {token_id} not found in Genuine Undead collection'
                }
                
        except Exception as e:
            return {'valid': False, 'reason': f'Validation failed: {str(e)}'}

async def run_daily_migration_detection(target_date: date = None) -> Dict:
    """Convenience function to run daily migration detection"""
    detector = MigrationDetector()
    return await detector.detect_daily_migrations(target_date)

def get_migration_analytics() -> Dict:
    """Get comprehensive migration analytics"""
    detector = MigrationDetector()
    
    try:
        migration_rate = detector.calculate_migration_rate()
        migration_summary = detector.get_migration_summary(30)  # Last 30 days
        
        return {
            'migration_rate': migration_rate,
            'monthly_summary': migration_summary,
            'last_updated': datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to get migration analytics: {e}")
        return {'error': str(e)}